from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.utils import timezone
from datetime import timedelta
from core.models import UserCompanion, GraduatedCompanion, Task, DepartmentGroup

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
