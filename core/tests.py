from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.utils import timezone
from datetime import timedelta
from core.models import (
    UserCompanion, GraduatedCompanion, Task, DepartmentGroup,
    IslandProfile, IslandItem, Achievement, UserAchievement,
    DepartmentBattle, DepartmentAchievement, DepartmentAchievementUnlock, DepartmentProfile
)
from core.services import (
    process_task_completion, ensure_initial_achievements, check_achievements,
    ensure_initial_department_achievements, check_department_achievements
)

class GamificationAndArchiveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123', is_staff=True)
        self.superuser = User.objects.create_superuser(username='admin', password='password123', email='admin@example.com')
        self.group = Group.objects.create(name='教務課')
        self.user.groups.add(self.group)
        self.client = Client()

    def test_user_companion_and_graduation(self):
        self.client.login(username='testuser', password='password123')
        companion = UserCompanion.objects.get(user=self.user)
        companion.companion_type = 'chick'
        companion.completed_tasks_count = 25
        companion.save()

        self.assertEqual(companion.level, 7)

        response = self.client.post('/graduate-companion/', {'new_companion_type': 'robot'})
        self.assertEqual(response.status_code, 302)

        companion.refresh_from_db()
        self.assertEqual(companion.companion_type, 'robot')
        self.assertEqual(companion.completed_tasks_count, 0)
        self.assertEqual(GraduatedCompanion.objects.filter(user=self.user).count(), 1)
        graduated = GraduatedCompanion.objects.get(user=self.user)
        self.assertEqual(graduated.companion_type, 'chick')
        self.assertEqual(graduated.completed_tasks_count, 25)

    def test_task_archiving(self):
        task = Task.objects.create(
            title='Test Task',
            description='Test Description',
            target_group=self.group,
            created_by=self.user,
            due_date=timezone.now().date(),
            is_archived=False
        )

        self.client.login(username='testuser', password='password123')
        response = self.client.get('/')
        self.assertContains(response, 'Test Task')

        task.is_archived = True
        task.save()

        response = self.client.get('/')
        self.assertNotContains(response, 'Test Task')

    def test_export_backup_superuser_only(self):
        self.client.login(username='testuser', password='password123')
        response = self.client.get('/export/json/')
        self.assertEqual(response.status_code, 302)

        self.client.login(username='admin', password='password123')
        response_json = self.client.get('/export/json/')
        self.assertEqual(response_json.status_code, 200)
        self.assertEqual(response_json['Content-Type'], 'application/json')

        response_csv = self.client.get('/export/csv/')
        self.assertEqual(response_csv.status_code, 200)
        self.assertIn('text/csv', response_csv['Content-Type'])

        import json
        backup_content = json.loads(response_json.content.decode('utf-8'))
        self.assertIn('task', backup_content)
        self.assertIn('user', backup_content)

    def test_multi_staff_and_dept_task_creation(self):
        user2 = User.objects.create_user(username='staff2', password='password123', last_name='山田', first_name='太郎', is_staff=True)
        user3 = User.objects.create_user(username='staff3', password='password123', last_name='佐藤', first_name='花子', is_staff=True)
        group2 = Group.objects.create(name='総務課')

        self.client.login(username='testuser', password='password123')

        # 複数教職員宛て起票テスト
        res1 = self.client.post('/', {
            'create_task': '1',
            'target_type': 'staff',
            'staff_mode': 'individual',
            'target_user_ids': [user2.id, user3.id],
            'title': '複数教職員宛てテスト',
            'description': '連絡事項です',
            'priority': 'mid',
            'due_date': str(timezone.now().date()),
            'privacy': 'sensitive',
        })
        self.assertEqual(res1.status_code, 302)
        task1 = Task.objects.get(title='複数教職員宛てテスト')
        self.assertEqual(task1.target_users.count(), 2)

        # 複数部署宛て起票テスト
        res2 = self.client.post('/', {
            'create_task': '1',
            'target_type': 'staff',
            'staff_mode': 'dept',
            'dept_target_group_ids': [self.group.id, group2.id],
            'title': '複数部署宛てテスト',
            'description': '部署連携テスト',
            'priority': 'high',
            'due_date': str(timezone.now().date()),
            'privacy': 'sensitive',
        })
        self.assertEqual(res2.status_code, 302)
        task2 = Task.objects.get(title='複数部署宛てテスト')
        self.assertEqual(task2.target_groups.count(), 2)

    def test_closed_tasks_archive_filter(self):
        self.client.login(username='testuser', password='password123')
        t1 = Task.objects.create(
            title='Normal Closed Task',
            description='Desc',
            target_group=self.group,
            created_by=self.user,
            due_date=timezone.now().date(),
            status='closed',
            is_archived=False
        )
        t2 = Task.objects.create(
            title='Archived Closed Task',
            description='Desc',
            target_group=self.group,
            created_by=self.user,
            due_date=timezone.now().date(),
            status='closed',
            is_archived=True
        )

        # 通常表示 (archive=unarchived)
        res_unarchived = self.client.get('/tasks/closed/?archive=unarchived')
        self.assertContains(res_unarchived, 'Normal Closed Task')
        self.assertNotContains(res_unarchived, 'Archived Closed Task')

        # アーカイブ済みのみ表示 (archive=archived)
        res_archived = self.client.get('/tasks/closed/?archive=archived')
        self.assertNotContains(res_archived, 'Normal Closed Task')
        self.assertContains(res_archived, 'Archived Closed Task')

        # すべて表示 (archive=all)
        res_all = self.client.get('/tasks/closed/?archive=all')
        self.assertContains(res_all, 'Normal Closed Task')
        self.assertContains(res_all, 'Archived Closed Task')

    def test_bulk_status_change_and_rewards(self):
        """ステータス一括変更と一括完了時のインセンティブ一回のみ付与テスト"""
        self.client.login(username='testuser', password='password123')
        t1 = Task.objects.create(
            title='Bulk Task 1',
            description='Desc',
            target_group=self.group,
            created_by=self.user,
            due_date=timezone.now().date(),
            status='open'
        )
        t2 = Task.objects.create(
            title='Bulk Task 2',
            description='Desc',
            target_group=self.group,
            created_by=self.user,
            due_date=timezone.now().date(),
            status='in_progress'
        )

        response = self.client.post('/', {
            'bulk_update_status': '1',
            'task_ids': [t1.id, t2.id],
            'bulk_status': 'closed'
        })
        self.assertEqual(response.status_code, 302)

        t1.refresh_from_db()
        t2.refresh_from_db()
        self.assertEqual(t1.status, 'closed')
        self.assertEqual(t2.status, 'closed')
        self.assertTrue(t1.reward_granted)
        self.assertTrue(t2.reward_granted)

        profile = IslandProfile.objects.get(user=self.user)
        self.assertEqual(profile.experience, 20)  # 10 * 2


class MyIslandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='islanduser', password='password123', is_staff=True)
        self.group = Group.objects.create(name='教務課')
        self.user.groups.add(self.group)
        self.client = Client()

    def test_island_profile_one_to_one(self):
        """IslandProfileがユーザーごとに1件だけ作成される"""
        profile = IslandProfile.objects.get(user=self.user)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.level, 1)
        self.assertEqual(profile.experience, 0)
        self.assertEqual(profile.coins, 0)
        self.assertEqual(profile.gacha_tickets, 0)
        with self.assertRaises(Exception):
            IslandProfile.objects.create(user=self.user)

    def test_task_completion_rewards_and_no_double_grant(self):
        """タスクをopen->closedにすると報酬付与され、再処理しても二重付与されない"""
        task = Task.objects.create(
            title='Reward Test Task',
            description='Test',
            target_group=self.group,
            created_by=self.user,
            due_date=timezone.now().date(),
            status='open'
        )

        self.client.login(username='islanduser', password='password123')

        # Update status to closed via view
        response = self.client.post(f'/task/{task.pk}/update/', {'status': 'closed'})
        self.assertEqual(response.status_code, 302)

        task.refresh_from_db()
        self.assertTrue(task.reward_granted)

        profile = IslandProfile.objects.get(user=self.user)
        companion = UserCompanion.objects.get(user=self.user)

        self.assertEqual(profile.experience, 10)
        self.assertEqual(profile.coins, 5)
        self.assertEqual(companion.completed_tasks_count, 1)

        # Try completing the same task again
        res2 = process_task_completion(task, self.user)
        self.assertFalse(res2)

        profile.refresh_from_db()
        companion.refresh_from_db()

        self.assertEqual(profile.experience, 10)
        self.assertEqual(profile.coins, 5)
        self.assertEqual(companion.completed_tasks_count, 1)

    def test_gacha_tickets_every_5_tasks(self):
        """5タスクごとにガチャチケットが増える"""
        self.client.login(username='islanduser', password='password123')

        for i in range(1, 11):
            t = Task.objects.create(
                title=f'Task {i}',
                description='Desc',
                target_group=self.group,
                created_by=self.user,
                due_date=timezone.now().date(),
                status='open'
            )
            process_task_completion(t, self.user)

        profile = IslandProfile.objects.get(user=self.user)
        companion = UserCompanion.objects.get(user=self.user)

        self.assertEqual(companion.completed_tasks_count, 10)
        self.assertEqual(profile.experience, 100)
        self.assertEqual(profile.coins, 50)
        self.assertEqual(profile.gacha_tickets, 2)

    def test_island_level_up(self):
        """島レベルが正しく上昇する"""
        profile = IslandProfile.objects.get(user=self.user)

        self.assertEqual(profile.level, 1)

        profile.experience = 40
        profile.update_level()
        profile.save()
        self.assertEqual(profile.level, 1)

        profile.experience = 50
        leveled, old_lv, new_lv = profile.update_level()
        profile.save()
        self.assertTrue(leveled)
        self.assertEqual(new_lv, 2)
        self.assertEqual(profile.level, 2)

        profile.experience = 120
        leveled, old_lv, new_lv = profile.update_level()
        profile.save()
        self.assertEqual(profile.level, 3)

        profile.experience = 220
        profile.update_level()
        profile.save()
        self.assertEqual(profile.level, 4)

        profile.experience = 350
        profile.update_level()
        profile.save()
        self.assertEqual(profile.level, 5)

    def test_gacha_draw_and_zero_ticket_check(self):
        """ガチャチケット消費と0枚時の拒否"""
        profile = IslandProfile.objects.get(user=self.user)
        self.client.login(username='islanduser', password='password123')

        res0 = self.client.post('/island/gacha/')
        self.assertEqual(res0.status_code, 302)
        self.assertEqual(IslandItem.objects.filter(user=self.user).count(), 0)

        profile.gacha_tickets = 1
        profile.save()

        res1 = self.client.post('/island/gacha/')
        self.assertEqual(res1.status_code, 302)

        profile.refresh_from_db()
        self.assertEqual(profile.gacha_tickets, 0)
        self.assertEqual(IslandItem.objects.filter(user=self.user).count(), 1)

        item = IslandItem.objects.get(user=self.user)
        self.assertTrue(item.is_placed)
        valid_item_types = list(dict(IslandItem.ITEM_TYPE_CHOICES).keys())
        self.assertIn(item.item_type, valid_item_types)

    def test_my_island_page_access(self):
        """マイアイランドページおよび表示のテスト"""
        self.client.login(username='islanduser', password='password123')
        res = self.client.get('/island/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'マイアイランド')
        self.assertContains(res, 'Lv. 1')


class AchievementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='achieveuser', password='password123', is_staff=True)
        self.group = Group.objects.create(name='教務課')
        self.user.groups.add(self.group)
        self.client = Client()
        ensure_initial_achievements()

    def test_task_count_achievements_and_no_duplicates(self):
        """10タスク完了で「はじめの一歩」、50タスク完了で「島の開拓者」が取得され重複登録されない"""
        self.client.login(username='achieveuser', password='password123')

        # 10件完了まで実行
        for i in range(1, 11):
            t = Task.objects.create(
                title=f'Achievement Task {i}',
                description='Desc',
                target_group=self.group,
                created_by=self.user,
                due_date=timezone.now().date(),
                status='open'
            )
            process_task_completion(t, self.user)

        ua_10 = UserAchievement.objects.filter(user=self.user, achievement__code='TASK_10')
        self.assertEqual(ua_10.count(), 1)
        self.assertEqual(ua_10.first().achievement.name, 'はじめの一歩')

        # 重複チェックのコール
        check_achievements(self.user)
        self.assertEqual(UserAchievement.objects.filter(user=self.user, achievement__code='TASK_10').count(), 1)

        # 50件完了まで追加実行
        for i in range(11, 51):
            t = Task.objects.create(
                title=f'Achievement Task {i}',
                description='Desc',
                target_group=self.group,
                created_by=self.user,
                due_date=timezone.now().date(),
                status='open'
            )
            process_task_completion(t, self.user)

        ua_50 = UserAchievement.objects.filter(user=self.user, achievement__code='TASK_50')
        self.assertEqual(ua_50.count(), 1)
        self.assertEqual(ua_50.first().achievement.name, '島の開拓者')

    def test_change_title_and_dashboard_display(self):
        """称号を変更でき、Dashboardおよび実績ページに反映される"""
        self.client.login(username='achieveuser', password='password123')

        # 10件完了して実績「TASK_10」を取得
        for i in range(1, 11):
            t = Task.objects.create(
                title=f'Task {i}',
                description='Desc',
                target_group=self.group,
                created_by=self.user,
                due_date=timezone.now().date(),
                status='open'
            )
            process_task_completion(t, self.user)

        ach = Achievement.objects.get(code='TASK_10')

        # 称号を変更
        res_set = self.client.post('/achievements/set-title/', {'achievement_id': ach.id})
        self.assertEqual(res_set.status_code, 302)

        profile = IslandProfile.objects.get(user=self.user)
        self.assertEqual(profile.current_title, ach)

        # Dashboardに現在の称号が表示される
        res_dash = self.client.get('/')
        self.assertContains(res_dash, 'はじめの一歩')
        self.assertContains(res_dash, '実績を見る')

        # 実績ページで達成済み・未達成を確認できる
        res_ach = self.client.get('/achievements/')
        self.assertEqual(res_ach.status_code, 200)
        self.assertContains(res_ach, 'はじめの一歩')
        self.assertContains(res_ach, '熟練開拓者')  # 未達成リストに表示


class DepartmentBossTests(TestCase):
    def setUp(self):
        self.group1 = Group.objects.create(name='営業部')
        self.group2 = Group.objects.create(name='開発部')

        self.user1 = User.objects.create_user(username='sales_user', password='password123', is_staff=True)
        self.user1.groups.add(self.group1)

        self.user2 = User.objects.create_user(username='dev_user', password='password123', is_staff=True)
        self.user2.groups.add(self.group2)

        self.client = Client()

    def test_task_completion_reduces_boss_hp_by_priority(self):
        """target_group付きTaskがclosedになるとボスHPが優先度に応じて減少する"""
        battle = DepartmentBattle.objects.create(
            department=self.group1,
            boss_name='納期ドラゴン',
            max_hp=1000,
            current_hp=1000,
            status='active'
        )

        task_high = Task.objects.create(
            title='High Priority Task',
            description='Desc',
            target_group=self.group1,
            created_by=self.user1,
            due_date=timezone.now().date(),
            priority='high',
            status='open'
        )

        process_task_completion(task_high, self.user1)
        battle.refresh_from_db()
        self.assertEqual(battle.current_hp, 900)  # 1000 - 100

        task_mid = Task.objects.create(
            title='Mid Priority Task',
            description='Desc',
            target_group=self.group1,
            created_by=self.user1,
            due_date=timezone.now().date(),
            priority='mid',
            status='open'
        )
        process_task_completion(task_mid, self.user1)
        battle.refresh_from_db()
        self.assertEqual(battle.current_hp, 850)  # 900 - 50

        task_low = Task.objects.create(
            title='Low Priority Task',
            description='Desc',
            target_group=self.group1,
            created_by=self.user1,
            due_date=timezone.now().date(),
            priority='low',
            status='open'
        )
        process_task_completion(task_low, self.user1)
        battle.refresh_from_db()
        self.assertEqual(battle.current_hp, 825)  # 850 - 25

    def test_task_without_target_group_does_not_affect_boss(self):
        """target_groupがないTaskではボスHPが減らない"""
        battle = DepartmentBattle.objects.create(
            department=self.group1,
            boss_name='会議ロボ',
            max_hp=1000,
            current_hp=1000,
            status='active'
        )

        task_no_group = Task.objects.create(
            title='No Group Task',
            description='Desc',
            target_group=None,
            created_by=self.user1,
            due_date=timezone.now().date(),
            priority='high',
            status='open'
        )

        process_task_completion(task_no_group, self.user1)
        battle.refresh_from_db()
        self.assertEqual(battle.current_hp, 1000)

    def test_no_double_damage_on_same_task(self):
        """同じTaskで二重ダメージが発生しない"""
        battle = DepartmentBattle.objects.create(
            department=self.group1,
            boss_name='タスクモンスター',
            max_hp=1000,
            current_hp=1000,
            status='active'
        )

        task = Task.objects.create(
            title='Double Damage Test',
            description='Desc',
            target_group=self.group1,
            created_by=self.user1,
            due_date=timezone.now().date(),
            priority='high',
            status='open'
        )

        res1 = process_task_completion(task, self.user1)
        self.assertTrue(res1)
        battle.refresh_from_db()
        self.assertEqual(battle.current_hp, 900)

        res2 = process_task_completion(task, self.user1)
        self.assertFalse(res2)
        battle.refresh_from_db()
        self.assertEqual(battle.current_hp, 900)

    def test_boss_status_becomes_defeated_when_hp_reaches_zero(self):
        """HPが0になるとstatus=defeatedになり、次のボスが自動生成される"""
        battle = DepartmentBattle.objects.create(
            department=self.group1,
            boss_name='締切ゴーレム',
            max_hp=100,
            current_hp=100,
            status='active'
        )

        task = Task.objects.create(
            title='Final Hit Task',
            description='Desc',
            target_group=self.group1,
            created_by=self.user1,
            due_date=timezone.now().date(),
            priority='high',  # 100 damage
            status='open'
        )

        process_task_completion(task, self.user1)
        battle.refresh_from_db()
        self.assertEqual(battle.current_hp, 0)
        self.assertEqual(battle.status, 'defeated')
        self.assertIsNotNone(battle.end_date)

        # 自動的に新しいアクティブなボスが生成されていることを確認
        new_active_boss = DepartmentBattle.objects.filter(department=self.group1, status='active').first()
        self.assertIsNotNone(new_active_boss)
        self.assertNotEqual(new_active_boss.id, battle.id)

        # 部署実績の解除チェック
        unlock = DepartmentAchievementUnlock.objects.filter(department=self.group1, achievement__code='DEPT_DEFEAT_1')
        self.assertTrue(unlock.exists())

    def test_dashboard_and_boss_view_permissions(self):
        """Dashboardの簡易表示と閲覧権限・アクセス制御のテスト"""
        battle = DepartmentBattle.objects.create(
            department=self.group1,
            boss_name='納期ドラゴン',
            max_hp=1000,
            current_hp=800,
            status='active'
        )

        # 所属メンバー (user1) ログイン
        self.client.login(username='sales_user', password='password123')
        dash_res = self.client.get('/')
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, '納期ドラゴン')
        self.assertContains(dash_res, 'HP 800/1000')

        # 自分の部署ボス画面閲覧可能
        dept_res = self.client.get(f'/department/{self.group1.id}/boss/')
        self.assertEqual(dept_res.status_code, 200)
        self.assertContains(dept_res, '納期ドラゴン')

        # 他部署メンバー (user2) ログイン
        self.client.login(username='dev_user', password='password123')

        # 他部署詳細の閲覧拒否（PermissionDenied: 403）
        forbidden_res = self.client.get(f'/department/{self.group1.id}/boss/')
        self.assertEqual(forbidden_res.status_code, 403)


class DashboardFailSafeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='freshuser', password='password123', is_staff=True)
        self.client = Client()

    def test_dashboard_renders_with_zero_data(self):
        """DBデータやタスク・キャラが0件であってもダッシュボードが正常に200でレンダリングされ、枠組みが表示される"""
        self.client.login(username='freshuser', password='password123')
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)

        # 必須のベースUI要素が存在することを検証
        self.assertContains(response, 'Cross-Campus Task Hub')
        self.assertContains(response, '要対応タスク一覧')
        self.assertContains(response, '今後の対応予定タスク（0件）')
        self.assertContains(response, '現在対応が必要なタスクはありません。')
        self.assertContains(response, 'モチベーション:')

        # アコーディオン本体が初期状態から展開状態 (collapse show) であることを検証
        self.assertContains(response, 'id="normalTasksBody" class="collapse show"')
        self.assertContains(response, 'id="normalHeader"')
        self.assertContains(response, 'aria-expanded="true"')

        # フェールセーフ用の表示保障CSSが含まれることを検証
        self.assertContains(response, 'opacity: 1 !important')
        self.assertContains(response, 'display: block !important')

    def test_dashboard_renders_with_urgent_and_normal_tasks(self):
        """至急タスクおよび通常タスクが存在する場合に正しく展開状態でレンダリングされる"""
        group = Group.objects.create(name='教務課')
        self.user.groups.add(group)

        today = timezone.now().date()
        Task.objects.create(
            title='Urgent Task 1',
            description='Urgent Desc',
            target_group=group,
            created_by=self.user,
            due_date=today,
            status='open'
        )
        Task.objects.create(
            title='Normal Task 1',
            description='Normal Desc',
            target_group=group,
            created_by=self.user,
            due_date=today + timedelta(days=2),
            status='open'
        )

        self.client.login(username='freshuser', password='password123')
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Urgent Task 1')
        self.assertContains(response, 'Normal Task 1')
        self.assertContains(response, 'id="urgentTasksBody" class="collapse show"')
        self.assertContains(response, 'id="normalTasksBody" class="collapse show"')
