from django.contrib import messages
from .models import UserCompanion, IslandProfile


def process_task_completion(task, user, request=None):
    """
    タスク完了（closed）時の一括インセンティブ処理。
    - 二重付与防止: task.reward_granted が True の場合はスキップ
    - UserCompanion.completed_tasks_count +1
    - IslandProfile.experience +10, coins +5
    - 経験値に応じた島レベル更新（Lv1:0, Lv2:50, Lv3:120, Lv4:220, Lv5:350）
    - 5タスク完了ごとにガチャチケット+1枚
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

    if request:
        messages.success(request, "✨ タスク完了報酬を獲得しました！（EXP +10, コイン +5）")

    return True
