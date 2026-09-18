import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aiwa.settings')
django.setup()

from django.contrib.auth.models import User, Group
from core.models import StaffDuty, StaffProfile

def run():
    print("教職員ダミーデータを作成開始...")

    # 1. 部署・担当業務の構造定義
    dept_structure = {
        '事務局': ['総務', '経理', '人事', '施設管理'],
        '教務部': ['情報IT科', '国際ビジネス科', 'ホテル観光科', '学籍管理'],
        '就職課': ['キャリア支援', 'インターンシップ', '企業連携'],
        '広報課': ['オープンキャンパス', 'SNS・Web運用', '高校訪問'],
    }

    group_objs = {}
    duty_objs = {}

    for group_name, duties in dept_structure.items():
        grp, _ = Group.objects.get_or_create(name=group_name)
        group_objs[group_name] = grp
        duty_objs[group_name] = {}
        for duty_name in duties:
            d, _ = StaffDuty.objects.get_or_create(department_group=grp, name=duty_name)
            duty_objs[group_name][duty_name] = d

    # 2. 教職員データ（兼務・複数担当を含む）
    staff_data_list = [
        {'username': 'sato_j', 'last': '佐藤', 'first': '純一', 'dept': '事務局', 'duties': ['総務', '人事']},
        {'username': 'suzuki_k', 'last': '鈴木', 'first': '恵子', 'dept': '事務局', 'duties': ['経理']},
        {'username': 'takahashi_m', 'last': '高橋', 'first': '誠', 'dept': '教務部', 'duties': ['情報IT科', '学籍管理']},
        {'username': 'tanaka_y', 'last': '田中', 'first': '由美', 'dept': '教務部', 'duties': ['国際ビジネス科']},
        {'username': 'watanabe_d', 'last': '渡辺', 'first': '大輔', 'dept': '教務部', 'duties': ['ホテル観光科']},
        {'username': 'ito_k', 'last': '伊藤', 'first': '健二', 'dept': '就職課', 'duties': ['キャリア支援', '企業連携']},
        {'username': 'yamamoto_a', 'last': '山本', 'first': 'あおい', 'dept': '就職課', 'duties': ['キャリア支援', 'インターンシップ']},
        {'username': 'nakamura_r', 'last': '中村', 'first': '亮太', 'dept': '広報課', 'duties': ['オープンキャンパス', 'SNS・Web運用']},
        # 複数部署・兼務の例（教務と広報、事務局と就職課）
        {'username': 'kobayashi_t', 'last': '小林', 'first': '拓也', 'dept': '教務部', 'duties': ['情報IT科'], 'extra_duties': [('広報課', '高校訪問')]},
        {'username': 'kato_m', 'last': '加藤', 'first': '美穂', 'dept': '事務局', 'duties': ['総務'], 'extra_duties': [('就職課', 'キャリア支援')]},
    ]

    for data in staff_data_list:
        user, created = User.objects.get_or_create(
            username=data['username'],
            defaults={
                'last_name': data['last'],
                'first_name': data['first'],
                'email': f"{data['username']}@aiwa.ac.jp",
                'is_staff': True,
            }
        )
        if created:
            user.set_password('staffpass123')
            user.save()

        # 所属グループの付与
        main_grp = group_objs[data['dept']]
        user.groups.add(main_grp)

        # プロファイルの作成・更新
        profile, _ = StaffProfile.objects.get_or_create(user=user)
        profile.department_group = main_grp

        selected_duties = [duty_objs[data['dept']][d_name] for d_name in data['duties']]
        if 'extra_duties' in data:
            for extra_dept, extra_duty_name in data['extra_duties']:
                selected_duties.append(duty_objs[extra_dept][extra_duty_name])
                user.groups.add(group_objs[extra_dept])

        profile.duties.set(selected_duties)
        profile.save()

    print("教職員ダミーデータの登録が完了しました。")

if __name__ == '__main__':
    run()