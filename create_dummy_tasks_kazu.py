import os
import django
import random
from datetime import timedelta
from django.utils import timezone

# Django設定の初期化
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aiwa.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Task, Student

def run():
    target_username = 'kazu'
    try:
        user = User.objects.get(username=target_username)
    except User.DoesNotExist:
        print(f"エラー: ユーザー '{target_username}' が見つかりません。")
        return

    # 起票者（作成者）用のアカウント（他ユーザー、いなければkazu自身）
    other_users = list(User.objects.exclude(username=target_username))
    creator_pool = other_users if other_users else [user]

    # 紐づけ可能な学生リスト
    students = list(Student.objects.all())

    # タスクの業務バリエーション
    task_templates = [
        ("就職活動の履歴書・自己PR添削", "応募前書類の確認を行い、フィードバックを実施してください。"),
        ("企業推薦書の発行手続き", "推薦状の作成と押印申請を行ってください。"),
        ("面接練習（模擬面接）の実施", "入室マナーから志望動機・質疑応答のトレーニングを行います。"),
        ("未提出書類（誓約書・健康診断票）の催促", "本人へ連絡し、今週中の提出を指示してください。"),
        ("欠席・遅刻超過に関する指導面談", "出席率改善のための個別フォロー面談を実施してください。"),
        ("合同企業説明会の参加状況確認", "エントリーシートの提出状況および当日の出席を確認してください。"),
        ("内定承諾書の受理と報告", "企業からの受諾連絡を確認し、進路決定登録を行ってください。"),
        ("学生相談（進路・生活面）の対応記録", "面談記録を作成し、担任教員へ情報共有してください。"),
        ("作品ポートフォリオのレビュー", "企業提出用作品集のクオリティチェックと講評をお願いします。"),
        ("資格検定試験の受験案内・申込確認", "申込締切前にアナウンスと取りまとめを行ってください。"),
        ("インターンシップ受入先との日程調整", "企業担当者様へ連絡し、受入スケジュールのすり合わせを行ってください。"),
        ("保護者面談のスケジュール調整", "保護者様へアポイントを取り、面談日程を確定させてください。"),
    ]

    priorities = ['high', 'medium', 'low']
    statuses = ['todo', 'in_progress', 'completed']
    privacy_levels = ['general', 'sensitive']

    today = timezone.now().date()
    created_tasks = []

    print(f"--- ユーザー '{user.get_full_name() or user.username}' 宛てのタスク生成を開始 (100件) ---")

    for i in range(1, 101):
        tmpl_title, tmpl_desc = random.choice(task_templates)
        title = f"【依頼】{tmpl_title} (#{i:03d})"
        
        # 期日のバリエーション（過去2週間 〜 未来3週間）
        due_offset = random.randint(-14, 21)
        due_date = today + timedelta(days=due_offset)

        # 優先度・ステータス
        priority = random.choices(priorities, weights=[25, 55, 20])[0]
        status = random.choices(statuses, weights=[50, 30, 20])[0]
        privacy = random.choices(privacy_levels, weights=[75, 25])[0]
        
        created_by = random.choice(creator_pool)

        # タスク生成（単一外部キー target_user）
        task = Task(
            title=title,
            description=f"{tmpl_desc}\n（自動生成ダミーデータ）",
            due_date=due_date,
            priority=priority,
            status=status,
            privacy=privacy,
            created_by=created_by,
            target_user=user,
        )

        # is_archived フィールドが存在する場合はセット
        if hasattr(task, 'is_archived'):
            # 完了かつ古いものは一部アーカイブ扱いに
            if status == 'completed' and due_offset < -5:
                task.is_archived = random.choice([True, False])
            else:
                task.is_archived = False

        task.save()

        # ManyToManyField の target_users にも追加（複数宛て改修対応）
        if hasattr(task, 'target_users'):
            task.target_users.add(user)

        # 70%の確率で学生を1〜3名紐づけ
        if students and random.random() < 0.7:
            sample_count = min(len(students), random.randint(1, 3))
            selected_students = random.sample(students, sample_count)
            task.students.set(selected_students)

        created_tasks.append(task)

    print(f"✅ 完了: 井本 和浩（kazu）宛てのダミータスクを {len(created_tasks)} 件登録しました！")

if __name__ == '__main__':
    run()