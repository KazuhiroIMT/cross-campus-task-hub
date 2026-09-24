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
from .models import Task, TaskComment, Student, TaskStudentProgress, Department, Course, SchoolClass, UserCompanion, GraduatedCompanion
from .forms import TaskCreateForm, CSVUploadForm


def get_accessible_tasks(user):
    """ユーザーが閲覧可能なタスクを取得する共通ベースクエリ

    ・スーパーユーザーであっても日常業務の一覧画面では他人の個人宛て機密案件を除外
    ・自身が起票、自身宛て（target_user/assigned_user）、または個人指定のない自部署宛て案件のみを抽出
    """
    user_groups = user.groups.all()

    base_condition = (
        Q(created_by=user)
        | Q(assigned_user=user)
        | Q(target_user=user)
        | (Q(target_group__in=user_groups) & Q(target_user__isnull=True))
    )
    return Task.objects.filter(base_condition)


@login_required
def dashboard(request):
    user = request.user

    # Ensure companion exists for existing users
    companion = getattr(user, 'usercompanion', None)
    if not companion:
        from .models import UserCompanion
        UserCompanion.objects.get_or_create(user=user)
    user_groups = user.groups.all()
    today = timezone.now().date()

    # 1. 閲覧可能なタスクを取得
    accessible_tasks = (
        get_accessible_tasks(user)
        .filter(is_archived=False)
        .exclude(status='closed')
        .select_related(
            'target_group', 'created_by', 'assigned_user', 'target_user'
        )
        .prefetch_related('students')
    )

    # 自分宛て、自分担当、または「個人指定のない自部署宛て案件」のみをダッシュボードに表示
    my_tasks = accessible_tasks.filter(
        Q(assigned_user=user)
        | Q(target_user=user)
        | (Q(target_group__in=user_groups) & Q(target_user__isnull=True))
    )

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
            Q(assigned_user__first_name__icontains=norm_q) |
            Q(assigned_user__last_name__icontains=norm_q) |
            Q(assigned_user__username__icontains=norm_q) |
            Q(created_by__first_name__icontains=norm_q) |
            Q(created_by__last_name__icontains=norm_q) |
            Q(created_by__username__icontains=norm_q) |
            Q(target_group__name__icontains=norm_q)
        )

        # 3. 日付検索対応（「9/22」や「9-22」を月・日に分解して検索）
        match = re.fullmatch(r'(\d{1,2})[/.-](\d{1,2})', norm_q)
        if match:
            m, d = int(match.group(1)), int(match.group(2))
            search_condition |= Q(due_date__month=m, due_date__day=d)
            search_condition |= Q(created_at__month=m, created_at__day=d)

        my_tasks = my_tasks.filter(search_condition).distinct()

    urgent_tasks = my_tasks.filter(due_date__lte=today).order_by(
        'due_date', '-priority'
    )
    normal_tasks_qs = my_tasks.filter(due_date__gt=today).order_by(
        'due_date', '-priority'
    )

    normal_tasks_count = normal_tasks_qs.count()

    paginator = Paginator(normal_tasks_qs, 20)
    page_number = request.GET.get('page')
    normal_tasks = paginator.get_page(page_number)

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
                target_user_id = request.POST.get('target_user_id')
                if not target_user_id:
                    messages.error(request, '対象教職員を選択してください。')
                    return redirect('dashboard')

                target_user = get_object_or_404(User, pk=target_user_id)

                # 宛先部署の特定
                target_group = None
                if (
                    hasattr(target_user, 'staff_profile')
                    and target_user.staff_profile.department_group
                ):
                    target_group = target_user.staff_profile.department_group
                elif user_groups.exists():
                    target_group = user_groups.first()
                else:
                    target_group = Group.objects.first()

                # target_group を渡してNOT NULL制約エラーを防止
                Task.objects.create(
                    target_type='staff',
                    target_user=target_user,
                    assigned_user=target_user,
                    target_group=target_group,
                    title=title,
                    description=description,
                    priority=priority,
                    due_date=due_date,
                    privacy='sensitive',
                    created_by=user,
                )
                messages.success(
                    request,
                    f'{target_user.get_full_name() or target_user.username} 宛ての教職員タスクを起票しました。',
                )

            else:
                dept_group_id = request.POST.get('dept_target_group')
                if not dept_group_id:
                    messages.error(request, '宛先部署を選択してください。')
                    return redirect('dashboard')

                target_group = get_object_or_404(Group, pk=dept_group_id)
                selected_duties = request.POST.getlist('selected_duties')
                desc = description
                if selected_duties:
                    desc = f"【担当業務: {', '.join(selected_duties)}】\n" + desc

                Task.objects.create(
                    target_type='staff',
                    target_group=target_group,
                    title=title,
                    description=desc,
                    priority=priority,
                    due_date=due_date,
                    privacy='sensitive',
                    created_by=user,
                )
                messages.success(
                    request, f'【{target_group.name}】宛ての教職員タスクを起票しました。'
                )

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

    context = {
        'urgent_tasks': urgent_tasks,
        'normal_tasks': normal_tasks,
        'normal_tasks_count': normal_tasks_count,
        'today': today,
        'staffs': staffs,
        'groups': groups,
        'departments': departments,
        'dept_class_map_json': dept_class_map_json,
        'search_query': search_query,
        'graduated_companions': graduated_companions,
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
        is_target_user = (task.target_user == user)
        # 部署宛て（個人指定なし）の場合のみ部署メンバーに閲覧を許可
        is_target_group = (task.target_group in user_groups and task.target_user is None)
        
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
                companion, created = getattr(request.user, 'usercompanion', None), False
                if not companion:
                    from .models import UserCompanion
                    companion, created = UserCompanion.objects.get_or_create(user=request.user)
                if companion:
                    companion.completed_tasks_count += 1
                    companion.save()

        messages.success(request, '対応内容を保存しました。')
        return redirect('task_detail', pk=task.pk)

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

    closed_tasks_qs = get_accessible_tasks(user).filter(
        is_archived=False
    ).filter(
        Q(assigned_user=user) | 
        Q(target_user=user) | 
        (Q(target_group__in=user_groups) & Q(target_user__isnull=True))
    ).filter(status='closed').select_related(
        'target_group', 
        'created_by', 
        'assigned_user', 
        'target_user'
    ).prefetch_related('students')

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
                companion, created = getattr(request.user, 'usercompanion', None), False
                if not companion:
                    from .models import UserCompanion
                    companion, created = UserCompanion.objects.get_or_create(user=request.user)
                if companion:
                    companion.completed_tasks_count += 1
                    companion.save()
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

    tasks = tasks.order_by('due_date', '-priority')
    
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
    tasks = Task.objects.all()
    data = serializers.serialize('json', tasks, ensure_ascii=False, indent=2)
    response = HttpResponse(data, content_type='application/json')
    filename = f"task_backup_{timezone.now():%Y%m%d_%H%M%S}.json"
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

    for task in Task.objects.select_related('target_group', 'created_by').all():
        writer.writerow([
            task.id,
            task.title,
            task.get_target_type_display(),
            task.target_group.name if task.target_group else '',
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
