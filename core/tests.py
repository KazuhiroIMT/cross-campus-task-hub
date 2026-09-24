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
