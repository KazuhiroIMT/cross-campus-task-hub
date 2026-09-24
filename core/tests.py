from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.utils import timezone
from datetime import timedelta
from core.models import UserCompanion, GraduatedCompanion, Task, DepartmentGroup, IslandProfile, IslandItem, Achievement, UserAchievement
from core.services import process_task_completion, ensure_initial_achievements, check_achievements

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

        self.assertEqual(companion.level, 4)

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
        self.assertIn(item.item_type, ['tree', 'flower', 'rock', 'house', 'fountain', 'shop', 'animal', 'castle'])

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
