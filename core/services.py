from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from .models import (
    UserCompanion, IslandProfile, Achievement, UserAchievement,
    UserTaskCompletionDate, IslandItem, DepartmentBattle,
    DepartmentAchievement, DepartmentAchievementUnlock, DepartmentProfile
)

# ボス候補テンプレート（自動生成用）
BOSS_TEMPLATES = [
    {'boss_type': 'dragon', 'boss_name': '納期ドラゴン', 'max_hp': 1000},
    {'boss_type': 'robot', 'boss_name': '業務整理ロボ', 'max_hp': 1200},
    {'boss_type': 'monster', 'boss_name': '書類モンスター', 'max_hp': 1500},
    {'boss_type': 'golem', 'boss_name': '未対応ゴーレム', 'max_hp': 2000},
]


def ensure_active_department_boss(department):
    """
    指定された部署にアクティブなボスが存在しない場合、自動的に次のボスを安全に生成する。
    同時実行などで重複生成が起きないようトランザクションとアトミックロックを使用。
    """
    if not department:
        return None

    active_boss = DepartmentBattle.objects.filter(
        department=department,
        status='active'
    ).first()

    if active_boss:
        return active_boss

    with transaction.atomic():
        # 再チェック（排他ロック付き）
        active_boss = DepartmentBattle.objects.select_for_update().filter(
            department=department,
            status='active'
        ).first()

        if active_boss:
            return active_boss

        # 過去の討伐数に応じてボステンプレートを選択
        defeated_count = DepartmentBattle.objects.filter(
            department=department,
            status='defeated'
        ).count()

        template = BOSS_TEMPLATES[defeated_count % len(BOSS_TEMPLATES)]
        count_suffix = f" (第{defeated_count + 1}世代)" if defeated_count > 0 else ""

        new_boss = DepartmentBattle.objects.create(
            department=department,
            boss_type=template['boss_type'],
            boss_name=f"{template['boss_name']}{count_suffix}",
            max_hp=template['max_hp'],
            current_hp=template['max_hp'],
            status='active',
            start_date=timezone.now()
        )
        return new_boss

# Priority damage constants
BOSS_DAMAGE_MAP = {
    'high': 100,
    'mid': 50,
    'low': 25,
}


def ensure_initial_department_achievements():
    """初期の部署実績データの作成/登録"""
    initial_dept_achievements = [
        {
            'code': 'DEPT_DEFEAT_1',
            'name': '初めての討伐',
            'description': '部署で初めてボスを討伐する',
            'requirement_type': 'DEFEAT_COUNT',
            'requirement_value': 1,
        },
        {
            'code': 'DEPT_DEFEAT_5',
            'name': '討伐隊',
            'description': '部署でボスを累計5体討伐する',
            'requirement_type': 'DEFEAT_COUNT',
            'requirement_value': 5,
        },
        {
            'code': 'DEPT_DEFEAT_10',
            'name': '精鋭討伐隊',
            'description': '部署でボスを累計10体討伐する',
            'requirement_type': 'DEFEAT_COUNT',
            'requirement_value': 10,
        },
    ]

    for item in initial_dept_achievements:
        DepartmentAchievement.objects.get_or_create(
            code=item['code'],
            defaults={
                'name': item['name'],
                'description': item['description'],
                'requirement_type': item['requirement_type'],
                'requirement_value': item['requirement_value'],
            }
        )


def check_department_achievements(department, request=None):
    """部署実績のチェックと付与"""
    ensure_initial_department_achievements()

    unlocked_ids = set(
        DepartmentAchievementUnlock.objects.filter(department=department).values_list('achievement_id', flat=True)
    )

    defeated_count = DepartmentBattle.objects.filter(department=department, status='defeated').count()
    dept_profile, _ = DepartmentProfile.objects.get_or_create(department=department)

    achievements = DepartmentAchievement.objects.all()

    for ach in achievements:
        if ach.id in unlocked_ids:
            continue

        is_achieved = False
        if ach.requirement_type == 'DEFEAT_COUNT' and defeated_count >= ach.requirement_value:
            is_achieved = True

        if is_achieved:
            _, created = DepartmentAchievementUnlock.objects.get_or_create(
                department=department,
                achievement=ach
            )
            if created:
                unlocked_ids.add(ach.id)
                if not dept_profile.current_title:
                    dept_profile.current_title = ach
                    dept_profile.save(update_fields=['current_title'])

                if request:
                    messages.info(request, f"🛡️ 部署実績解除（{department.name}）：{ach.name}")


def ensure_initial_achievements():
    """初期実績データの作成/登録"""
    initial_achievements = [
        {
            'code': 'TASK_10',
            'name': 'はじめの一歩',
            'description': 'タスクを10件完了する',
            'category': 'TASK_COUNT',
            'requirement_value': 10,
        },
        {
            'code': 'TASK_50',
            'name': '島の開拓者',
            'description': 'タスクを50件完了する',
            'category': 'TASK_COUNT',
            'requirement_value': 50,
        },
        {
            'code': 'TASK_100',
            'name': '熟練開拓者',
            'description': 'タスクを100件完了する',
            'category': 'TASK_COUNT',
            'requirement_value': 100,
        },
        {
            'code': 'STREAK_7',
            'name': '継続の達人',
            'description': '7日連続でタスクを完了する',
            'category': 'STREAK',
            'requirement_value': 7,
        },
        {
            'code': 'ISLAND_LV5',
            'name': '島主',
            'description': '島レベルが5に到達する',
            'category': 'ISLAND_LEVEL',
            'requirement_value': 5,
        },
        {
            'code': 'GACHA_10',
            'name': 'コレクター',
            'description': 'ガチャを10回引く',
            'category': 'GACHA',
            'requirement_value': 10,
        },
    ]

    for item in initial_achievements:
        Achievement.objects.get_or_create(
            code=item['code'],
            defaults={
                'name': item['name'],
                'description': item['description'],
                'category': item['category'],
                'requirement_value': item['requirement_value'],
            }
        )


def calculate_user_streak(user):
    """ユーザーの連続タスク完了日数を計算"""
    dates = list(
        UserTaskCompletionDate.objects.filter(user=user)
        .order_by('-date')
        .values_list('date', flat=True)
    )
    if not dates:
        return 0

    today = timezone.now().date()
    yesterday = today - timedelta(days=1)

    if dates[0] != today and dates[0] != yesterday:
        return 0

    streak = 1
    current = dates[0]
    for d in dates[1:]:
        if d == current - timedelta(days=1):
            streak += 1
            current = d
        elif d == current:
            continue
        else:
            break
    return streak


def check_achievements(user, request=None):
    """
    ユーザーの実績達成条件をチェックし、達成時にUserAchievementを登録してメッセージ表示
    """
    ensure_initial_achievements()

    unlocked_achievements = set(
        UserAchievement.objects.filter(user=user).values_list('achievement_id', flat=True)
    )

    companion = UserCompanion.objects.filter(user=user).first()
    task_count = companion.completed_tasks_count if companion else 0

    island_profile = IslandProfile.objects.filter(user=user).first()
    island_level = island_profile.level if island_profile else 1

    gacha_count = IslandItem.objects.filter(user=user).count()
    streak = calculate_user_streak(user)

    achievements = Achievement.objects.all()

    for ach in achievements:
        if ach.id in unlocked_achievements:
            continue

        is_achieved = False
        if ach.category == 'TASK_COUNT' and task_count >= ach.requirement_value:
            is_achieved = True
        elif ach.category == 'STREAK' and streak >= ach.requirement_value:
            is_achieved = True
        elif ach.category == 'ISLAND_LEVEL' and island_level >= ach.requirement_value:
            is_achieved = True
        elif ach.category == 'GACHA' and gacha_count >= ach.requirement_value:
            is_achieved = True

        if is_achieved:
            _, created = UserAchievement.objects.get_or_create(
                user=user,
                achievement=ach
            )
            if created:
                unlocked_achievements.add(ach.id)
                # デフォルトの称号が未設定の場合、最初に解除した実績を自動セット（任意）
                if island_profile and not island_profile.current_title:
                    island_profile.current_title = ach
                    island_profile.save(update_fields=['current_title'])

                if request:
                    messages.info(request, f"🏆 実績解除：{ach.name}")


def process_task_completion(task, user, request=None):
    """
    タスク完了（closed）時の一括インセンティブおよび実績チェック処理。
    - 二重付与防止: task.reward_granted が True の場合はスキップ
    - UserCompanion.completed_tasks_count +1
    - IslandProfile.experience +10, coins +5
    - 経験値に応じた島レベル更新（Lv1:0, Lv2:50, Lv3:120, Lv4:220, Lv5:350）
    - 5タスク完了ごとにガチャチケット+1枚
    - UserTaskCompletionDate 記録 & 実績チェック (Task -> Rewards -> Achievement check)
    """
    if task.reward_granted:
        return False

    # 1. 重複付与防止フラグ更新
    task.reward_granted = True
    task.save(update_fields=['reward_granted'])

    # 2. 育成キャラクター完了カウント更新
    companion, _ = UserCompanion.objects.get_or_create(user=user)
    companion.completed_tasks_count += 1
    companion.save()

    # 3. アイランドプロファイル更新
    profile, _ = IslandProfile.objects.get_or_create(user=user)
    profile.experience += 10
    profile.coins += 5

    # 4. レベルアップ確認
    leveled_up, old_lv, new_lv = profile.update_level()
    if leveled_up and request:
        messages.success(request, f"🏝️ 島がLv.{new_lv}になりました！")

    # 5. ガチャチケット付与 (5タスクごとに1枚)
    if companion.completed_tasks_count > 0 and companion.completed_tasks_count % 5 == 0:
        profile.gacha_tickets += 1
        if request:
            messages.info(request, "🎟️ 5件完了達成！ガチャチケットを1枚獲得しました！")

    profile.save()

    # 6. タスク完了日の記録
    today = timezone.now().date()
    UserTaskCompletionDate.objects.get_or_create(user=user, date=today)

    if request:
        messages.success(request, "✨ タスク完了報酬を獲得しました！（EXP +10, コイン +5）")

    # 7. 実績達成チェック
    check_achievements(user, request=request)

    # 8. 部署ボスへのダメージ処理（target_groupが指定されている場合）
    if task.target_group:
        target_dept = task.target_group
        active_battle = DepartmentBattle.objects.filter(
            department=target_dept,
            status='active'
        ).first()

        if active_battle:
            damage = BOSS_DAMAGE_MAP.get(task.priority, 50)
            active_battle.current_hp -= damage

            if active_battle.current_hp <= 0:
                active_battle.current_hp = 0
                active_battle.status = 'defeated'
                active_battle.end_date = timezone.now()
                active_battle.save()

                if request:
                    messages.success(request, f"🎉 {active_battle.boss_name}討伐！ ({target_dept.name})")

                check_department_achievements(target_dept, request=request)
                # ボス撃破時、自動的に次のボスを生成
                ensure_active_department_boss(target_dept)
            else:
                active_battle.save()
                if request:
                    messages.info(request, f"⚔️ 部署ボス（{active_battle.boss_name}）に {damage} ダメージを与えました！（残りHP: {active_battle.current_hp}/{active_battle.max_hp}）")

    return True
