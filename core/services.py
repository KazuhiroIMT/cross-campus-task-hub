from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from .models import (
    UserCompanion, IslandProfile, Achievement, UserAchievement,
    UserTaskCompletionDate, IslandItem, DepartmentBattle,
    DepartmentAchievement, DepartmentAchievementUnlock, DepartmentProfile
)

import random

# ドラゴンボス30段階マスタ設計（業務・タスクモチーフ）
BOSS_TEMPLATES = [
    {'boss_level': 1,  'boss_type': 'dragon', 'boss_name': 'コドモドラゴ（未着手タスクの幼体）', 'max_hp': 1000, 'image_path': 'core/images/bosses/dragon_01.png'},
    {'boss_level': 2,  'boss_type': 'dragon', 'boss_name': 'メモリーワイバーン（連絡漏れの使い魔）', 'max_hp': 2500, 'image_path': 'core/images/bosses/dragon_02.png'},
    {'boss_level': 3,  'boss_type': 'dragon', 'boss_name': 'ケアレスリザード（記入ミス・誤字脱字竜）', 'max_hp': 4500, 'image_path': 'core/images/bosses/dragon_03.png'},
    {'boss_level': 4,  'boss_type': 'dragon', 'boss_name': 'スケジュールパピー（日程重複の幼竜）', 'max_hp': 7000, 'image_path': 'core/images/bosses/dragon_04.png'},
    {'boss_level': 5,  'boss_type': 'dragon', 'boss_name': '催促のフライヤー（提出物未回収の飛竜）', 'max_hp': 10000, 'image_path': 'core/images/bosses/dragon_05.png'},
    {'boss_level': 6,  'boss_type': 'dragon', 'boss_name': '保留のドレイク（ペンディング案件の沼竜）', 'max_hp': 14000, 'image_path': 'core/images/bosses/dragon_06.png'},
    {'boss_level': 7,  'boss_type': 'dragon', 'boss_name': '欠席ラッシュドラゴン（突発対応の咆哮竜）', 'max_hp': 19000, 'image_path': 'core/images/bosses/dragon_07.png'},
    {'boss_level': 8,  'boss_type': 'dragon', 'boss_name': '事務処理ゴーンドラゴン（書類山積の岩石竜）', 'max_hp': 25000, 'image_path': 'core/images/bosses/dragon_08.png'},
    {'boss_level': 9,  'boss_type': 'dragon', 'boss_name': '面談過密のスピリット（スケジュール逼迫竜）', 'max_hp': 32000, 'image_path': 'core/images/bosses/dragon_09.png'},
    {'boss_level': 10, 'boss_type': 'dragon', 'boss_name': '納期ドラゴン・幼生（期限切迫の赤翼竜）', 'max_hp': 40000, 'image_path': 'core/images/bosses/dragon_10.png'},
    {'boss_level': 11, 'boss_type': 'dragon', 'boss_name': 'システムエラーワイバーン（連携障害の雷竜）', 'max_hp': 50000, 'image_path': 'core/images/bosses/dragon_11.png'},
    {'boss_level': 12, 'boss_type': 'dragon', 'boss_name': '期日超過のケルベロスドラゴン（追跡困難の猛竜）', 'max_hp': 62000, 'image_path': 'core/images/bosses/dragon_12.png'},
    {'boss_level': 13, 'boss_type': 'dragon', 'boss_name': '怒涛の行事ラダー（学校行事ピークの嵐竜）', 'max_hp': 76000, 'image_path': 'core/images/bosses/dragon_13.png'},
    {'boss_level': 14, 'boss_type': 'dragon', 'boss_name': '評価ラッシュファング（成績・レポート査定の激竜）', 'max_hp': 92000, 'image_path': 'core/images/bosses/dragon_14.png'},
    {'boss_level': 15, 'boss_type': 'dragon', 'boss_name': '多重案件のヒドラ（タスク同時多発の多頭竜）', 'max_hp': 110000, 'image_path': 'core/images/bosses/dragon_15.png'},
    {'boss_level': 16, 'boss_type': 'dragon', 'boss_name': '締切プレッシャーベヒモス（最終期限の鉄壁竜）', 'max_hp': 132000, 'image_path': 'core/images/bosses/dragon_16.png'},
    {'boss_level': 17, 'boss_type': 'dragon', 'boss_name': 'キャパシティオーバーロード（業務限界の灼熱竜）', 'max_hp': 158000, 'image_path': 'core/images/bosses/dragon_17.png'},
    {'boss_level': 18, 'boss_type': 'dragon', 'boss_name': 'インシデント・ドゥーム（緊急事態対応の獄炎竜）', 'max_hp': 190000, 'image_path': 'core/images/bosses/dragon_18.png'},
    {'boss_level': 19, 'boss_type': 'dragon', 'boss_name': '終末のタスクカタストロフィ（学期末総決算の破壊竜）', 'max_hp': 230000, 'image_path': 'core/images/bosses/dragon_19.png'},
    {'boss_level': 20, 'boss_type': 'dragon', 'boss_name': 'アビス・エンドライン（完全納期崩壊を司る絶対の深淵古龍）', 'max_hp': 300000, 'image_path': 'core/images/bosses/dragon_20.png'},
    {'boss_level': 21, 'boss_type': 'dragon', 'boss_name': '新学期ラッシュドラゴン（新年度準備の始動竜）', 'max_hp': 350000, 'image_path': 'core/images/bosses/dragon_21.png'},
    {'boss_level': 22, 'boss_type': 'dragon', 'boss_name': '予算査定バハムート（財政逼迫の金竜）', 'max_hp': 400000, 'image_path': 'core/images/bosses/dragon_22.png'},
    {'boss_level': 23, 'boss_type': 'dragon', 'boss_name': '監査襲来ファブニル（証跡要求の漆黒竜）', 'max_hp': 460000, 'image_path': 'core/images/bosses/dragon_23.png'},
    {'boss_level': 24, 'boss_type': 'dragon', 'boss_name': '大規模障害レヴィアタン（インフラ停止の水龍）', 'max_hp': 530000, 'image_path': 'core/images/bosses/dragon_24.png'},
    {'boss_level': 25, 'boss_type': 'dragon', 'boss_name': '年次総括ヴリトラ（年間業務集大成の巨竜）', 'max_hp': 600000, 'image_path': 'core/images/bosses/dragon_25.png'},
    {'boss_level': 26, 'boss_type': 'dragon', 'boss_name': '超過勤務オメガドラゴン（限界突破の極光竜）', 'max_hp': 680000, 'image_path': 'core/images/bosses/dragon_26.png'},
    {'boss_level': 27, 'boss_type': 'dragon', 'boss_name': '無限再提出ニーズヘッグ（永久ループの蝕竜）', 'max_hp': 770000, 'image_path': 'core/images/bosses/dragon_27.png'},
    {'boss_level': 28, 'boss_type': 'dragon', 'boss_name': '絶対絶命バハムート・アルファ（破滅的納期の覇竜）', 'max_hp': 870000, 'image_path': 'core/images/bosses/dragon_28.png'},
    {'boss_level': 29, 'boss_type': 'dragon', 'boss_name': 'カオスデッドライン（時空崩壊の暗黒竜）', 'max_hp': 980000, 'image_path': 'core/images/bosses/dragon_29.png'},
    {'boss_level': 30, 'boss_type': 'dragon', 'boss_name': 'ラグナロク・タスクマザー（全タスクの根源にして終焉の神龍）', 'max_hp': 1200000, 'image_path': 'core/images/bosses/dragon_30.png'},
]

# ランダムボス3種（HPは一律 7777）
RANDOM_BOSS_TEMPLATES = [
    {'boss_level': 0, 'boss_type': 'random_boss', 'boss_name': 'はぐれタスクキング（幻のレアモンスター）', 'max_hp': 7777, 'image_path': 'core/images/bosses/random_boss_01.png'},
    {'boss_level': 0, 'boss_type': 'random_boss', 'boss_name': 'ラッキー・ゴールドゴーザ（黄金の気まぐれ魔神）', 'max_hp': 7777, 'image_path': 'core/images/bosses/random_boss_02.png'},
    {'boss_level': 0, 'boss_type': 'random_boss', 'boss_name': 'カオス・タスクチェンジ（変幻自在の混沌獣）', 'max_hp': 7777, 'image_path': 'core/images/bosses/random_boss_03.png'},
]


def ensure_active_department_boss(department):
    """
    指定された部署にアクティブなボス（または休憩中）が存在しない場合、自動的に次のボスを安全に生成する。
    ・当日討伐済みの場合は即時出現させず、「recess」状態（recess.png）を維持。
    ・日付が変わった（翌日以降）アクセス時に新しいボスを出現。
    ・周回モード時は全33種（通常30＋ランダム3）から完全ランダム選出。
    """
    if not department:
        return None

    today = timezone.localdate()
    dept_profile, _ = DepartmentProfile.objects.get_or_create(department=department)

    # 1. 進行中(active) または 休憩中(recess) のレコードを確認
    active_boss = DepartmentBattle.objects.filter(
        department=department,
        status__in=['active', 'recess']
    ).first()

    if active_boss:
        # 休憩中レコードが存在する場合、日付が変わったか判定
        if active_boss.status == 'recess':
            if active_boss.last_defeated_date and active_boss.last_defeated_date == today:
                return active_boss  # 当日中は休憩中を継続
            # 翌日になったので、recess レコードを defeated に変更して次ボス生成へ進む
            active_boss.status = 'defeated'
            active_boss.save(update_fields=['status'])
        else:
            return active_boss

    # 2. 当日既にボスを撃破済みで、まだ active / recess が無い場合（直接訪問等）
    last_defeated_date = dept_profile.last_defeated_date
    if not last_defeated_date:
        last_defeated_boss = DepartmentBattle.objects.filter(
            department=department,
            status='defeated'
        ).order_by('-end_date', '-id').first()
        if last_defeated_boss and last_defeated_boss.last_defeated_date:
            last_defeated_date = last_defeated_boss.last_defeated_date

    if last_defeated_date == today:
        # 当日撃破済みの場合は休憩中(recess)レコードを生成・返却
        recess_boss = DepartmentBattle.objects.create(
            department=department,
            boss_type='recess',
            boss_level=0,
            boss_name='本日の討伐完了（休憩中）',
            max_hp=0,
            current_hp=0,
            status='recess',
            last_defeated_date=today,
            start_date=timezone.now()
        )
        return recess_boss

    with transaction.atomic():
        # 再チェック（排他ロック付き）
        active_boss = DepartmentBattle.objects.select_for_update().filter(
            department=department,
            status__in=['active', 'recess']
        ).first()

        if active_boss:
            if active_boss.status == 'recess':
                if active_boss.last_defeated_date and active_boss.last_defeated_date == today:
                    return active_boss
                active_boss.status = 'defeated'
                active_boss.save(update_fields=['status'])
            else:
                return active_boss

        # 次に出現させるボステンプレートの選定
        if dept_profile.is_loop_mode:
            # 周回（カオス）モード: 全33種（通常30 + ランダム3）から完全ランダム選出
            all_options = BOSS_TEMPLATES + RANDOM_BOSS_TEMPLATES
            template = random.choice(all_options)
            boss_level = template.get('boss_level', 0)
        else:
            # 通常進行（Lv.1 ～ Lv.30）
            defeated_count = DepartmentBattle.objects.filter(
                department=department,
                status='defeated'
            ).exclude(boss_type='recess').count()

            level_index = min(defeated_count, len(BOSS_TEMPLATES) - 1)
            template = BOSS_TEMPLATES[level_index]
            boss_level = template['boss_level']

        new_boss = DepartmentBattle.objects.create(
            department=department,
            boss_type=template['boss_type'],
            boss_level=boss_level,
            boss_name=template['boss_name'],
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
        {
            'code': 'DEPT_DRAGON_CONQUEROR',
            'name': '巨龍の征服者',
            'description': 'Lv.30の最終ボスドラゴンを撃破する',
            'requirement_type': 'SPECIAL',
            'requirement_value': 30,
        },
        {
            'code': 'DEPT_TASK_HAOU',
            'name': 'タスクの覇王',
            'description': '全てのドラゴンボスを討伐し周回モードへと到達する',
            'requirement_type': 'SPECIAL',
            'requirement_value': 30,
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
                today = timezone.localdate()
                active_battle.current_hp = 0
                active_battle.status = 'defeated'
                active_battle.end_date = timezone.now()
                active_battle.last_defeated_date = today
                active_battle.save()

                dept_profile, _ = DepartmentProfile.objects.get_or_create(department=target_dept)
                dept_profile.last_defeated_date = today

                if request:
                    messages.success(request, f"🎉 {active_battle.boss_name}討伐！ ({target_dept.name}) 本日の討伐が完了しました！")

                # Lv.30 ボス撃破時の処理（称号付与 & 周回モード移行）
                if active_battle.boss_level == 30 and active_battle.boss_type == 'dragon':
                    dept_profile.is_loop_mode = True

                    # 称号付与（巨龍の征服者 / タスクの覇王）
                    ensure_initial_department_achievements()
                    conqueror_ach = DepartmentAchievement.objects.filter(code='DEPT_DRAGON_CONQUEROR').first()
                    haou_ach = DepartmentAchievement.objects.filter(code='DEPT_TASK_HAOU').first()

                    if conqueror_ach:
                        DepartmentAchievementUnlock.objects.get_or_create(
                            department=target_dept,
                            achievement=conqueror_ach
                        )
                    if haou_ach:
                        DepartmentAchievementUnlock.objects.get_or_create(
                            department=target_dept,
                            achievement=haou_ach
                        )
                        if not dept_profile.current_title:
                            dept_profile.current_title = haou_ach

                    if request:
                        messages.success(request, f"🏆 祝・全30段階ボス制覇！特別称号「巨龍の征服者」「タスクの覇王」が解放され、周回（カオス）モードへ移行しました！")

                dept_profile.save()
                check_department_achievements(target_dept, request=request)

                # 当日討伐完了のため、本日は休憩中(recess)状態を生成・維持する
                ensure_active_department_boss(target_dept)
            else:
                active_battle.save()
                if request:
                    messages.info(request, f"⚔️ 部署ボス（{active_battle.boss_name}）に {damage} ダメージを与えました！（残りHP: {active_battle.current_hp}/{active_battle.max_hp}）")

    return True
