from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q

class Command(BaseCommand):
    help = '一定期間（デフォルト3日）ログインしていない教職員・ユーザーにリマインドメールを送信します（休暇中を除く）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=3,
            help='未ログインと判定する日数（デフォルト: 3）'
        )

    def handle(self, *args, **options):
        days = options['days']
        threshold_date = timezone.now() - timedelta(days=days)

        # 指定日数より前にログイン、または未ログインかつ登録から日数経過
        # かつ、休暇中（staff_profile__is_on_leave=True）のアカウントを除外
        inactive_users = User.objects.filter(
            is_active=True
        ).exclude(
            staff_profile__is_on_leave=True  # 休暇中のユーザーを除外
        ).filter(
            Q(last_login__lte=threshold_date) | 
            Q(last_login__isnull=True, date_joined__lte=threshold_date)
        ).exclude(email='')

        if not inactive_users.exists():
            self.stdout.write(self.style.SUCCESS(f'対象となる未ログインユーザー（{days}日以上、勤務中）はいません。'))
            return

        sent_count = 0
        for user in inactive_users:
            subject = '【Cross-Campus Task Hub】長期間ログインが確認されていません'
            name = f"{user.last_name} {user.first_name}".strip() or user.username
            last_login_str = user.last_login.strftime('%Y/%m/%d') if user.last_login else 'なし（初回ログイン前）'

            message = (
                f"{name} 先生・職員様\n\n"
                f"お疲れ様です。Cross-Campus Task Hub 管理事務局です。\n\n"
                f"本システムへの最終ログインから {days} 日以上が経過しているためご連絡いたしました。\n"
                f"（最終ログイン日時: {last_login_str}）\n\n"
                f"学内業務の申し送りやタスクの確認・起票のため、下記ポータルよりログインをお願いいたします。\n\n"
                f"--------------------------------------------------\n"
                f"■ Cross-Campus Task Hub ポータル\n"
                f"http://127.0.0.1:8000/\n"
                f"--------------------------------------------------\n\n"
                f"※本メールにお心当たりがない場合、またはパスワードをお忘れの場合は\n"
                f"システム管理者までお問い合わせください。\n"
            )

            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@aiwa.ac.jp',
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                sent_count += 1
                self.stdout.write(f"送信完了: {name} ({user.email})")
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"送信失敗: {user.username} - {e}"))

        self.stdout.write(self.style.SUCCESS(f'合計 {sent_count} 名に未ログインアラートを送信しました。'))