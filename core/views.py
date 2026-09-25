import csv
import io
import json
import unicodedata
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.core import serializers

# 必要なモデルを一括インポート（Student, TaskStudentProgress を含む）
from django.core.exceptions import PermissionDenied
from .models import Task, TaskComment, Student, TaskStudentProgress, Department, Course, SchoolClass, UserCompanion, GraduatedCompanion, StaffProfile, StaffDuty, IslandProfile, IslandItem, Achievement, UserAchievement, DepartmentBattle, DepartmentAchievement, DepartmentAchievementUnlock, DepartmentProfile
from .services import process_task_completion, ensure_initial_achievements, check_achievements, ensure_initial_department_achievements, check_department_achievements, ensure_active_department_boss
from .forms import TaskCreateForm, CSVUploadForm


def get_accessible_tasks(user):
    """ユーザーが閲覧可能なタスクを取得する共通ベースクエリ

    ・スーパーユーザーであっても日常業務の一覧画面では他人の個人宛て機密案件を除外
    ・自身が起票、自身宛て（target_user/target_users/assigned_user）、または個人指定のない自部署宛て案件のみを抽出
    """
    user_groups = user.groups.all()

    base_condition = (
        Q(created_by=user)
        | Q(assigned_user=user)
        | Q(target_user=user)
        | Q(target_users=user)
        | Q(target_group__in=user_groups)
        | Q(target_groups__in=user_groups)
    )
    return Task.objects.filter(base_condition).distinct()


@login_required
def department_boss(request, dept_id=None):
    """部署ボス討伐専用画面"""
    user = request.user
    user_groups = user.groups.all()

    if dept_id:
        department = get_object_or_404(Group, pk=dept_id)
    else:
        department = user_groups.first()
        if not department:
            messages.error(request, "所属部署が設定されていません。")
            return redirect('dashboard')

    # 他部署の詳細情報は不用意に閲覧させない権限チェック
    if not (user.is_superuser or department in user_groups):
        raise PermissionDenied("この部署のボス情報を閲覧する権限がありません。")

    ensure_initial_department_achievements()
    check_department_achievements(department)

    ensure_active_department_boss(department)
    dept_profile, _ = DepartmentProfile.objects.get_or_create(department=department)
    active_battle = DepartmentBattle.objects.filter(department=department, status='active').first()
    defeated_battles = DepartmentBattle.objects.filter(department=department, status='defeated').order_by('-end_date')

    unlocked_achievements_list = DepartmentAchievementUnlock.objects.filter(
        department=department
    ).select_related('achievement')

    context = {
        'department': department,
        'dept_profile': dept_profile,
        'active_battle': active_battle,
        'defeated_battles': defeated_battles,
        'unlocked_achievements_list': unlocked_achievements_list,
    }
    return render(request, 'core/department_boss.html', context)


@login_required
def set_department_title(request, dept_id):
    """部署称号の設定"""
    if request.method == 'POST':
        user = request.user
        department = get_object_or_404(Group, pk=dept_id)

        if not (user.is_superuser or department in user.groups.all()):
            raise PermissionDenied("部署称号を変更する権限がありません。")

        achievement_id = request.POST.get('achievement_id')
        dept_profile, _ = DepartmentProfile.objects.get_or_create(department=department)

        if not achievement_id or achievement_id == 'none':
            dept_profile.current_title = None
            dept_profile.save(update_fields=['current_title'])
            messages.success(request, "部署称号の設定を解除しました。")
        else:
            unlock = DepartmentAchievementUnlock.objects.filter(
                department=department,
                achievement_id=achievement_id
            ).select_related('achievement').first()

            if unlock:
                dept_profile.current_title = unlock.achievement
                dept_profile.save(update_fields=['current_title'])
                messages.success(request, f"部署称号を「🏆 {unlock.achievement.name}」に変更しました。")
            else:
                messages.error(request, "未達成の部署実績を称号に設定することはできません。")

    return redirect('department_boss', dept_id=dept_id)


@login_required
def dashboard(request):
    user = request.user

    # Ensure companion exists for existing users
    companion = getattr(user, 'usercompanion', None)
    if not companion:
        from .models import UserCompanion
        UserCompanion.objects.get_or_create(user=user)

    island_profile, _ = IslandProfile.objects.get_or_create(user=user)
    user_groups = user.groups.all()
    today = timezone.now().date()

    # 1. 一括ステータス変更アクションの処理
    if request.method == 'POST' and 'bulk_update_status' in request.POST:
        selected_task_ids = request.POST.getlist('task_ids')
        new_status = request.POST.get('bulk_status')
        if selected_task_ids and new_status in ['open', 'in_progress', 'closed']:
            target_tasks = get_accessible_tasks(user).filter(pk__in=selected_task_ids)
            updated_count = 0
            for t in target_tasks:
                old_status = t.status
                t.status = new_status
                t.save()
                if new_status == 'closed' and old_status != 'closed':
                    process_task_completion(t, user, request=None)
                updated_count += 1
            status_labels = {'open': '未着手', 'in_progress': '対応中', 'closed': '完了'}
            messages.success(request, f"{updated_count} 件のタスクを「{status_labels.get(new_status)}」に一括変更しました。")
            return redirect('dashboard')

    # 2. 閲覧可能な全アクティブタスクを取得
    accessible_tasks = (
        get_accessible_tasks(user)
        .filter(is_archived=False)
        .select_related(
            'target_group', 'created_by', 'assigned_user', 'target_user'
        )
        .prefetch_related('students', 'target_users', 'target_groups')
    )

    # 自分宛て、自分担当、または「個人指定のない自部署宛て案件」のみをダッシュボードに表示
    my_tasks = accessible_tasks.filter(
        Q(assigned_user=user)
        | Q(target_user=user)
        | Q(target_users=user)
        | Q(target_group__in=user_groups)
        | Q(target_groups__in=user_groups)
    ).distinct()

    # フリーワード検索
    search_query = request.GET.get('q', '').strip()
    if search_query:
        import unicodedata
        import re

        # 1. 検索ワードの正規化（半角カナを全角に統一し「ﾋﾞｼﾞﾈｽ」等に対応）
        norm_q = unicodedata.normalize('NFKC', search_query)

        # 2. テキスト項目全般への検索条件（タイトル、内容、学生、担当者、部署など）
        # ※外部キー項目は __name を追加して文字列として検索
        search_condition = (
            Q(title__icontains=norm_q) |
            Q(description__icontains=norm_q) |
            Q(completion_note__icontains=norm_q) |
            Q(students__name__icontains=norm_q) |
            Q(students__student_id__icontains=norm_q) |
            Q(students__furigana__icontains=norm_q) |
            Q(students__nickname__icontains=norm_q) |
            Q(students__department__name__icontains=norm_q) |
            Q(students__school_class__name__icontains=norm_q) |
            Q(target_user__first_name__icontains=norm_q) |
            Q(target_user__last_name__icontains=norm_q) |
            Q(target_user__username__icontains=norm_q) |
            Q(target_users__first_name__icontains=norm_q) |
            Q(target_users__last_name__icontains=norm_q) |
            Q(target_users__username__icontains=norm_q) |
            Q(assigned_user__first_name__icontains=norm_q) |
            Q(assigned_user__last_name__icontains=norm_q) |
            Q(assigned_user__username__icontains=norm_q) |
            Q(created_by__first_name__icontains=norm_q) |
            Q(created_by__last_name__icontains=norm_q) |
            Q(created_by__username__icontains=norm_q) |
            Q(target_group__name__icontains=norm_q) |
            Q(target_groups__name__icontains=norm_q)
        )

        # 3. 日付検索対応（「9/22」や「9-22」を月・日に分解して検索）
        match = re.fullmatch(r'(\d{1,2})[/.-](\d{1,2})', norm_q)
        if match:
            m, d = int(match.group(1)), int(match.group(2))
            search_condition |= Q(due_date__month=m, due_date__day=d)
            search_condition |= Q(created_at__month=m, created_at__day=d)

        my_tasks = my_tasks.filter(search_condition).distinct()

    from django.db.models import Case, When, Value, IntegerField

    priority_order = Case(
        When(priority='high', then=Value(1)),
        When(priority='mid', then=Value(2)),
        When(priority='low', then=Value(3)),
        default=Value(4),
        output_field=IntegerField(),
    )

    # 未完了案件と完了済み案件を分離
    active_my_tasks = my_tasks.exclude(status='closed')
    closed_my_tasks_qs = my_tasks.filter(status='closed').order_by('-updated_at')

    urgent_tasks_qs = active_my_tasks.filter(due_date__lte=today).annotate(
        priority_rank=priority_order
    ).order_by('due_date', 'priority_rank')

    normal_tasks_qs = active_my_tasks.filter(due_date__gt=today).annotate(
        priority_rank=priority_order
    ).order_by('due_date', 'priority_rank')

    urgent_tasks_count = urgent_tasks_qs.count()
    normal_tasks_count = normal_tasks_qs.count()
    closed_tasks_count = closed_my_tasks_qs.count()

    # 至急タスクの10件単位ページネーション
    urgent_paginator = Paginator(urgent_tasks_qs, 10)
    urgent_page_number = request.GET.get('urgent_page')
    urgent_tasks = urgent_paginator.get_page(urgent_page_number)

    # 今後予定タスクの10件単位ページネーション
    normal_paginator = Paginator(normal_tasks_qs, 10)
    normal_page_number = request.GET.get('page')
    normal_tasks = normal_paginator.get_page(normal_page_number)

    # 完了済み案件の10件単位ページネーション
    closed_paginator = Paginator(closed_my_tasks_qs, 10)
    closed_page_number = request.GET.get('closed_page')
    closed_tasks = closed_paginator.get_page(closed_page_number)

    # タスク起票処理
    if request.method == 'POST' and 'create_task' in request.POST:
        target_type = request.POST.get('target_type')
        title = request.POST.get('title')
        description = request.POST.get('description')
        priority = request.POST.get('priority', 'mid')
        due_date = request.POST.get('due_date')
        privacy = request.POST.get('privacy', 'general')

        if target_type == 'student':
            student_ids = request.POST.getlist('student_ids')
            target_group_id = request.POST.get('student_target_group')
            target_group = (
                get_object_or_404(Group, pk=target_group_id)
                if target_group_id
                else None
            )

            if not student_ids:
                messages.error(request, '対象学生を選択してください。')
                return redirect('dashboard')
            if not target_group:
                messages.error(request, '宛先部署を選択してください。')
                return redirect('dashboard')

            task = Task.objects.create(
                target_type='student',
                target_group=target_group,
                title=title,
                description=description,
                priority=priority,
                due_date=due_date,
                privacy=privacy,
                created_by=user,
            )
            task.students.set(student_ids)

            # 学生個別進捗がある場合は作成
            try:
                from .models import TaskStudentProgress

                for st_id in student_ids:
                    TaskStudentProgress.objects.get_or_create(task=task, student_id=st_id)
            except ImportError:
                pass

            messages.success(
                request, f'学生 {len(student_ids)} 名分のタスク（1件）を起票しました。'
            )
            return redirect('dashboard')

        elif target_type == 'staff':
            staff_mode = request.POST.get('staff_mode')

            if staff_mode == 'individual':
                target_user_ids = request.POST.getlist('target_user_ids')
                # もし単一選択の旧パラメータ target_user_id もあれば互換性のために拾う
                single_id = request.POST.get('target_user_id')
                if single_id and single_id not in target_user_ids:
                    target_user_ids.append(single_id)

                if not target_user_ids:
                    messages.error(request, '対象教職員を選択してください。')
                    return redirect('dashboard')

                selected_users = list(User.objects.filter(pk__in=target_user_ids))
                first_user = selected_users[0] if selected_users else None

                # 部署グループの特定
                depts = set()
                for u in selected_users:
                    if hasattr(u, 'staff_profile') and u.staff_profile.department_group:
                        depts.add(u.staff_profile.department_group)
                    for g in u.groups.all():
                        depts.add(g)

                primary_dept = list(depts)[0] if depts else (user_groups.first() or Group.objects.first())

                task = Task.objects.create(
                    target_type='staff',
                    target_user=first_user if len(selected_users) == 1 else None,
                    assigned_user=first_user if len(selected_users) == 1 else None,
                    target_group=primary_dept,
                    title=title,
                    description=description,
                    priority=priority,
                    due_date=due_date,
                    privacy='sensitive',
                    created_by=user,
                )
                task.target_users.set(selected_users)
                if depts:
                    task.target_groups.set(depts)

                if len(selected_users) == 1:
                    u_display = f"{first_user.last_name} {first_user.first_name}".strip() or first_user.username
                    messages.success(request, f'{u_display} 宛ての教職員タスクを起票しました。')
                else:
                    messages.success(request, f'教職員 {len(selected_users)} 名宛てのタスクを一括起票しました。')

            else:
                dept_group_ids = request.POST.getlist('dept_target_group_ids')
                single_dept_id = request.POST.get('dept_target_group')
                if single_dept_id and single_dept_id not in dept_group_ids:
                    dept_group_ids.append(single_dept_id)

                if not dept_group_ids:
                    messages.error(request, '宛先部署を選択してください。')
                    return redirect('dashboard')

                selected_groups = list(Group.objects.filter(pk__in=dept_group_ids))
                first_group = selected_groups[0] if selected_groups else None

                selected_duties = request.POST.getlist('selected_duties')
                desc = description
                if selected_duties:
                    desc = f"【担当業務: {', '.join(selected_duties)}】\n" + desc

                task = Task.objects.create(
                    target_type='staff',
                    target_group=first_group,
                    title=title,
                    description=desc,
                    priority=priority,
                    due_date=due_date,
                    privacy='sensitive',
                    created_by=user,
                )
                task.target_groups.set(selected_groups)

                if len(selected_groups) == 1:
                    messages.success(request, f'【{first_group.name}】宛ての教職員タスクを起票しました。')
                else:
                    messages.success(request, f'複数部署（{len(selected_groups)} 部署）宛ての教職員タスクを起票しました。')

            return redirect('dashboard')

    # 外部キーから名前を取得
    staffs = (
        User.objects.filter(is_active=True)
        .select_related('staff_profile__department_group')
        .prefetch_related('staff_profile__duties')
        .order_by('username')
    )
    groups = Group.objects.all().order_by('name')

    # 学科・クラスの文字列マップを構築
    students_for_map = Student.objects.filter(is_active=True).values(
        'department__name', 'school_class__name'
    )

    departments = sorted(
        list(
            set(
                s['department__name']
                for s in students_for_map
                if s['department__name']
            )
        )
    )
    dept_class_map = {}
    for st in students_for_map:
        d_name = st['department__name']
        c_name = st['school_class__name']
        if d_name and c_name:
            dept_class_map.setdefault(d_name, set()).add(c_name)

    import json

    dept_class_map_json = json.dumps(
        {k: sorted(list(v)) for k, v in dept_class_map.items()}, ensure_ascii=False
    )

    graduated_companions = GraduatedCompanion.objects.filter(user=user)

    # 部署ボスの簡易表示用データ
    user_primary_dept = user_groups.first()
    active_dept_battle = None
    if user_primary_dept:
        ensure_active_department_boss(user_primary_dept)
        active_dept_battle = DepartmentBattle.objects.filter(department=user_primary_dept, status='active').first()

    context = {
        'urgent_tasks': urgent_tasks,
        'urgent_tasks_count': urgent_tasks_count,
        'normal_tasks': normal_tasks,
        'normal_tasks_count': normal_tasks_count,
        'closed_tasks': closed_tasks,
        'closed_tasks_count': closed_tasks_count,
        'today': today,
        'staffs': staffs,
        'groups': groups,
        'departments': departments,
        'dept_class_map_json': dept_class_map_json,
        'search_query': search_query,
        'graduated_companions': graduated_companions,
        'island_profile': island_profile,
        'user_primary_dept': user_primary_dept,
        'active_dept_battle': active_dept_battle,
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def task_detail(request, pk):
    """タスク詳細（機密アクセス制御・学生進捗・戻るボタン対応）"""
    task = get_object_or_404(
        Task.objects.select_related(
            'target_group', 
            'created_by', 
            'assigned_user', 
            'target_user'
        ).prefetch_related('students'), 
        pk=pk
    )
    user = request.user
    user_groups = user.groups.all()

    # --- 1. 機密案件のアクセス制御チェック ---
    if task.privacy == 'sensitive':
        is_owner = (task.created_by == user)
        is_assigned = (task.assigned_user == user)
        is_target_user = (task.target_user == user or user in task.target_users.all())
        # 部署宛て（個人指定なし）の場合のみ部署メンバーに閲覧を許可
        is_target_group = (
            (task.target_group in user_groups and task.target_user is None and not task.target_users.exists())
            or any(g in user_groups for g in task.target_groups.all())
        )
        
        if not (user.is_superuser or is_owner or is_assigned or is_target_user or is_target_group):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("この案件は関係者限定の機密案件のため閲覧できません。")

    # --- 2. 学生案件の場合、進捗レコードが未生成なら補完 ---
    if task.target_type == 'student':
        for student in task.students.all():
            TaskStudentProgress.objects.get_or_create(task=task, student=student)

    # --- 3. 「戻る」ボタン用の遷移元URLをセッションに記憶 ---
    from django.urls import reverse
    session_key = f'task_back_url_{pk}'
    if request.method == 'GET':
        referer = request.META.get('HTTP_REFERER')
        # 自身（詳細画面）からのリロードや保存後のリダイレクトではない場合のみ記憶
        if referer and request.path not in referer:
            request.session[session_key] = referer

    # セッションからURLを取り出す（直接アクセス時などはダッシュボードをデフォルトに）
    back_url = request.session.get(session_key, reverse('dashboard'))

    # --- 4. フォーム送信（POST）処理 ---
    if request.method == 'POST':
        # ① 学生ごとの個別ステータス・メモの更新
        if 'update_student_progress' in request.POST:
            for progress in task.student_progresses.all():
                st_id = progress.student.id
                new_st_status = request.POST.get(f'student_status_{st_id}')
                new_st_memo = request.POST.get(f'student_memo_{st_id}', '').strip()
                if new_st_status:
                    progress.status = new_st_status
                progress.memo = new_st_memo
                progress.save()
            messages.success(request, '対象学生ごとの対応進捗を更新しました。')
            return redirect('task_detail', pk=task.pk)

        # ② 全体申し送りメモの追記＆ステータス更新
        comment_content = request.POST.get('comment', '').strip()
        new_status = request.POST.get('status')

        if comment_content:
            TaskComment.objects.create(
                task=task,
                author=user,
                content=comment_content
            )

        old_status = task.status
        if new_status and new_status in dict(Task.STATUS_CHOICES):
            task.status = new_status
            task.save()
            if new_status == 'closed' and old_status != 'closed':
                process_task_completion(task, user, request)

        messages.success(request, '対応内容を保存しました。')
        return redirect('dashboard')

    # --- 5. 画面表示（GET）処理 ---
    context = {
        'task': task,
        'comments': task.comments.select_related('author').all().order_by('created_at'),
        'student_progresses': task.student_progresses.select_related('student').order_by('student__student_id'),
        'back_url': back_url,  # テンプレートに記憶したURLを渡す
    }
    return render(request, 'core/task_detail.html', context)


@login_required
def my_created_tasks(request):
    """自分が依頼した案件一覧"""
    user = request.user
    search_query = request.GET.get('q', '').strip()

    tasks_qs = Task.objects.filter(created_by=user, is_archived=False).select_related(
        'target_group', 'assigned_user', 'target_user', 'created_by'
    ).prefetch_related('students')

    if search_query:
        tasks_qs = tasks_qs.filter(
            Q(students__name__icontains=search_query) |
            Q(students__student_id__icontains=search_query) |
            Q(title__icontains=search_query) |
            Q(target_group__name__icontains=search_query)
        ).distinct()

    tasks_qs = tasks_qs.order_by('-created_at')

    paginator = Paginator(tasks_qs, 20)
    page_number = request.GET.get('page')
    tasks = paginator.get_page(page_number)

    return render(request, 'core/my_created_tasks.html', {
        'tasks': tasks,
        'search_query': search_query,
    })


@login_required
def closed_task_list(request):
    """完了済みタスクの履歴アーカイブ"""
    user = request.user
    user_groups = user.groups.all()
    search_query = request.GET.get('q', '').strip()
    archive_filter = request.GET.get('archive', 'unarchived').strip()

    closed_tasks_qs = get_accessible_tasks(user).filter(
        Q(assigned_user=user) | 
        Q(target_user=user) | 
        Q(target_users=user) |
        Q(target_group__in=user_groups) |
        Q(target_groups__in=user_groups)
    ).filter(status='closed').select_related(
        'target_group', 
        'created_by', 
        'assigned_user', 
        'target_user'
    ).prefetch_related('students', 'target_users', 'target_groups')

    if archive_filter == 'archived':
        closed_tasks_qs = closed_tasks_qs.filter(is_archived=True)
    elif archive_filter == 'all':
        pass  # フィルタなし（両方表示）
    else:
        archive_filter = 'unarchived'
        closed_tasks_qs = closed_tasks_qs.filter(is_archived=False)

    if search_query:
        closed_tasks_qs = closed_tasks_qs.filter(
            Q(students__name__icontains=search_query) |
            Q(students__student_id__icontains=search_query) |
            Q(title__icontains=search_query)
        ).distinct()

    closed_tasks_qs = closed_tasks_qs.order_by('-updated_at')

    # 1ページあたり20件でページネーション
    paginator = Paginator(closed_tasks_qs, 20)
    page_number = request.GET.get('page')
    closed_tasks = paginator.get_page(page_number)

    return render(request, 'core/closed_tasks.html', {
        'closed_tasks': closed_tasks,
        'search_query': search_query,
        'archive_filter': archive_filter,
    })


@login_required
def update_task_status(request, pk):
    """一覧画面からの簡易ステータス変更"""
    task = get_object_or_404(Task, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['open', 'in_progress', 'closed']:
            old_status = task.status
            task.status = new_status
            task.save()
            if new_status == 'closed' and old_status != 'closed':
                process_task_completion(task, request.user, request)
            messages.success(request, f'案件「{task.title}」のステータスを更新しました。')
    return redirect('dashboard')


@login_required
def api_search_students(request):
    """学生検索用Ajax/JSON API（マスタ外部キー対応版）"""
    dept = request.GET.get('dept', '').strip()
    cls = request.GET.get('class_name', '').strip()
    q = request.GET.get('q', '').strip()

    # N+1問題を防止するため、マスタテーブル（外部キー）を事前に結合して取得
    students = Student.objects.filter(is_active=True).select_related('department', 'course', 'school_class')

    if dept:
        # 外部キー化されたため、department ではなく department__name で文字列検索
        students = students.filter(department__name=dept)
    if cls:
        # クラスも同様に school_class__name で検索
        students = students.filter(school_class__name=cls)
    if q:
        students = students.filter(
            Q(student_id__icontains=q) |
            Q(name__icontains=q) |
            Q(furigana__icontains=q) |
            Q(nickname__icontains=q)
        )

    student_list = []
    for s in students[:50]:
        student_list.append({
            'id': s.id,
            'student_id': s.student_id,
            'name': s.name,
            'display': s.modal_display,
            # 外部キーのオブジェクトそのものではなく、名前（文字列）を返す
            'department': s.department.name if s.department else '',
            'class_name': s.school_class.name if s.school_class else '',
        })

    return JsonResponse({'students': student_list})

@login_required
def other_department_tasks(request):
    """他部署の案件（一般公開可のみ）の一覧"""
    user = request.user
    user_groups = user.groups.all()
    search_query = request.GET.get('q', '').strip()

    # 1. 未完了（open, in_progress）
    # 2. プライバシー区分が「一般（general）」
    # 3. 宛先部署が自部署「以外」、担当が自分「以外」、起票者が自分「以外」
    tasks = Task.objects.filter(
        is_archived=False,
        status__in=['open', 'in_progress'],
        privacy='general'
    ).exclude(
        target_group__in=user_groups
    ).exclude(
        assigned_user=user
    ).exclude(
        created_by=user
    ).select_related(
        'target_group', 'assigned_user', 'target_user', 'created_by'
    ).prefetch_related(
        'students'
    )

    # 検索機能
    if search_query:
        tasks = tasks.filter(
            Q(student__name__icontains=search_query) |
            Q(student__student_id__icontains=search_query) |
            Q(title__icontains=search_query) |
            Q(target_group__name__icontains=search_query)
        )

    tasks = tasks.annotate(
        priority_rank=Case(
            When(priority='high', then=Value(1)),
            When(priority='mid', then=Value(2)),
            When(priority='low', then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )
    ).order_by('due_date', 'priority_rank')
    
    # ページネーション（1ページ20件）
    paginator = Paginator(tasks, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/other_department_tasks.html', {
        'tasks': page_obj,
        'search_query': search_query,
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def export_data_json(request):
    """スーパーユーザー限定：全タスク・関連データJSONエクスポート"""
    models_to_export = [
        Task, TaskStudentProgress, TaskComment, Student, User, StaffProfile,
        Group, Department, Course, SchoolClass
    ]
    backup_data = {}
    for model in models_to_export:
        key = model._meta.model_name
        qs = model.objects.all()
        backup_data[key] = json.loads(serializers.serialize('json', qs, ensure_ascii=False))

    data_str = json.dumps(backup_data, ensure_ascii=False, indent=2)
    response = HttpResponse(data_str, content_type='application/json')
    filename = f"task_backup_full_{timezone.now():%Y%m%d_%H%M%S}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@user_passes_test(lambda u: u.is_superuser)
def export_data_csv(request):
    """スーパーユーザー限定：全タスクデータCSVエクスポート"""
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename = f"task_backup_{timezone.now():%Y%m%d_%H%M%S}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        'ID', '件名', '対象種別', '担当部署', '優先度', 'ステータス',
        'プライバシー区分', '対応期日', '起票者', 'アーカイブ状態', '作成日時'
    ])

    for task in Task.objects.prefetch_related('target_groups', 'target_users', 'students').select_related('target_group', 'target_user', 'created_by').all():
        writer.writerow([
            task.id,
            task.title,
            task.get_target_type_display(),
            task.target_groups_display,
            task.get_priority_display(),
            task.get_status_display(),
            task.get_privacy_display(),
            task.due_date,
            task.created_by.username,
            'アーカイブ済' if task.is_archived else '通常',
            task.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        ])

    return response


@login_required
def select_companion(request):
    if request.method == 'POST':
        companion_type = request.POST.get('companion_type')
        from .models import UserCompanion
        companion, created = UserCompanion.objects.get_or_create(user=request.user)
        if companion_type in dict(UserCompanion.COMPANION_CHOICES).keys():
            companion.companion_type = companion_type
            companion.save()
            messages.success(request, '育成キャラクターを選択しました。')
    return redirect('dashboard')


@login_required
def graduate_companion(request):
    if request.method == 'POST':
        new_companion_type = request.POST.get('new_companion_type')
        companion, created = UserCompanion.objects.get_or_create(user=request.user)

        if companion.level >= 4 and companion.companion_type != 'none':
            # 卒業（殿堂入り）記録を作成
            GraduatedCompanion.objects.create(
                user=request.user,
                companion_type=companion.companion_type,
                completed_tasks_count=companion.completed_tasks_count
            )

            # 育成キャラクターと完了数をリセットして新キャラ（または未選択）へ変更
            valid_choices = dict(UserCompanion.COMPANION_CHOICES).keys()
            companion.companion_type = new_companion_type if new_companion_type in valid_choices else 'none'
            companion.completed_tasks_count = 0
            companion.save()
            messages.success(request, 'キャラクターが殿堂入りしました！新しいキャラクターの育成がスタートします。')
        else:
            messages.error(request, 'まだ最大レベルに達していません。')
    return redirect('dashboard')


import random

@login_required
def my_island(request):
    """マイアイランド管理画面"""
    profile, _ = IslandProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST' and 'toggle_item_placed' in request.POST:
        item_id = request.POST.get('item_id')
        item = get_object_or_404(IslandItem, pk=item_id, user=request.user)
        item.is_placed = not item.is_placed
        item.save()
        status_str = "配置" if item.is_placed else "非配置"
        messages.success(request, f"アイテム「{item.name}」を{status_str}にしました。")
        return redirect('my_island')

    items = IslandItem.objects.filter(user=request.user)
    placed_items = items.filter(is_placed=True)

    context = {
        'island_profile': profile,
        'items': items,
        'placed_items': placed_items,
    }
    return render(request, 'core/island.html', context)


@login_required
def gacha_page(request):
    """ガチャ画面"""
    profile, _ = IslandProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        if profile.gacha_tickets < 1:
            messages.error(request, "ガチャチケットが足りません。タスクを完了してチケットを獲得してください。")
            return redirect('gacha_page')

        profile.gacha_tickets -= 1
        profile.save()

        ITEM_CHOICES = [
            ('tree', '🌲 立派な樹木'),
            ('flower', '🌸 綺麗なお花'),
            ('rock', '🪨 風情のある大岩'),
            ('house', '🏠 快適なコテージ'),
            ('fountain', '⛲ 癒やしの噴水'),
            ('shop', '🏪 賑やかなショップ'),
            ('animal', '🐶 かわいい動物'),
            ('castle', '🏰 ミニチュア城'),
        ]

        item_type, item_name = random.choice(ITEM_CHOICES)
        IslandItem.objects.create(
            user=request.user,
            item_type=item_type,
            name=item_name,
            is_placed=True
        )

        from .services import check_achievements
        check_achievements(request.user, request=request)

        messages.success(request, f"🎉 ガチャ成功！「{item_name}」を獲得しました！")
        return redirect('gacha_page')

    items = IslandItem.objects.filter(user=request.user)

    context = {
        'island_profile': profile,
        'items': items,
    }
    return render(request, 'core/gacha.html', context)


@login_required
def achievements_page(request):
    """実績・称号専用ページ"""
    ensure_initial_achievements()
    check_achievements(request.user)

    user = request.user
    island_profile, _ = IslandProfile.objects.get_or_create(user=user)

    all_achievements = Achievement.objects.all()
    user_achievements = UserAchievement.objects.filter(user=user).select_related('achievement')
    achieved_map = {ua.achievement_id: ua.achieved_at for ua in user_achievements}

    achieved_list = []
    unachieved_list = []

    for ach in all_achievements:
        if ach.id in achieved_map:
            achieved_list.append({
                'achievement': ach,
                'achieved_at': achieved_map[ach.id],
                'is_current': island_profile.current_title_id == ach.id,
            })
        else:
            unachieved_list.append({
                'achievement': ach,
            })

    context = {
        'island_profile': island_profile,
        'achieved_list': achieved_list,
        'unachieved_list': unachieved_list,
    }
    return render(request, 'core/achievements.html', context)


@login_required
def set_current_title(request):
    """称号の設定/解除"""
    if request.method == 'POST':
        achievement_id = request.POST.get('achievement_id')
        island_profile, _ = IslandProfile.objects.get_or_create(user=request.user)

        if not achievement_id or achievement_id == 'none':
            island_profile.current_title = None
            island_profile.save(update_fields=['current_title'])
            messages.success(request, "称号の設定を解除しました。")
        else:
            ua = UserAchievement.objects.filter(user=request.user, achievement_id=achievement_id).select_related('achievement').first()
            if ua:
                island_profile.current_title = ua.achievement
                island_profile.save(update_fields=['current_title'])
                messages.success(request, f"称号を「🏆 {ua.achievement.name}」に変更しました。")
            else:
                messages.error(request, "未達成の実績を称号に設定することはできません。")

    return redirect('achievements_page')


@login_required
def api_get_island_data(request):
    """島データ取得用Ajax API"""
    user = request.user
    profile, _ = IslandProfile.objects.get_or_create(user=user)
    items = IslandItem.objects.filter(user=user)

    items_data = []
    for item in items:
        items_data.append({
            'id': item.id,
            'name': item.name,
            'item_type': item.item_type,
            'icon': item.icon,
            'position_x': item.position_x,
            'position_y': item.position_y,
            'position_z': item.position_z,
            'rotation_y': item.rotation_y,
            'is_placed': item.is_placed,
        })

    data = {
        'island': {
            'level': profile.level,
            'experience': profile.experience,
            'next_level_exp': profile.next_level_exp,
            'exp_progress_percent': profile.exp_progress_percent,
            'coins': profile.coins,
            'gacha_tickets': profile.gacha_tickets,
        },
        'items': items_data,
    }
    return JsonResponse(data)


@login_required
def api_save_placed_items(request):
    """配置変更非同期保存用Ajax API"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid HTTP method'}, status=405)

    try:
        body = json.loads(request.body)
        items_payload = body.get('items', [])

        user = request.user
        user_item_ids = set(IslandItem.objects.filter(user=user).values_list('id', flat=True))

        updated_count = 0
        for item_info in items_payload:
            item_id = item_info.get('id')
            if item_id in user_item_ids:
                item = IslandItem.objects.get(pk=item_id, user=user)
                item.position_x = float(item_info.get('position_x', 0.0))
                item.position_y = float(item_info.get('position_y', 0.0))
                item.position_z = float(item_info.get('position_z', 0.0))
                item.rotation_y = float(item_info.get('rotation_y', 0.0))
                item.is_placed = bool(item_info.get('is_placed', True))
                item.save()
                updated_count += 1

        return JsonResponse({'status': 'success', 'updated_count': updated_count})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
