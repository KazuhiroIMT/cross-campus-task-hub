from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import UserCompanion, IslandProfile, Achievement, UserAchievement, UserTaskCompletionDate, IslandItem


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

    return True
