import os
import random
from datetime import date, timedelta
import django

# Django環境の初期化
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aiwa.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from core.models import Task, Student

User = get_user_model()

# 担当教職員（起票者および個人宛ての対象者: 5名限定）
STAFF_USERNAMES = ['ito_k', 'kato_m', 'kazu', 'kobayashi_t', 'nakamura_r']

# =========================================================
# ★Gitのモデル定義から正しいキーを動的に取得するヘルパー関数★
# =========================================================
def get_choice_key(model_class, field_name, display_text):
    """
    モデルの choices から「未着手」や「高」などの表示名に一致する
    DB保存用の正しい内部キーを自動的に抽出します。
    """
    field = model_class._meta.get_field(field_name)
    if getattr(field, 'choices', None):
        for key, display in field.choices:
            if display_text in str(display):
                return key
        return field.choices[0][0] # 見つからない場合は最初のキーをデフォルト
    return display_text # choices定義がない場合はそのまま返す

# タスク種別テンプレート（部署・優先度・業務内容）
# ※ priority は画面の選択肢に合わせて「高」「中」「低」で定義
TEMPLATES = {
    "GROUP": [
        {"title": "【教務課】シラバス更新・入力締め切り通知", "description": "来期の科目シラバスの最終確認と登録を完了させてください。", "dept": "教務課", "priority": "高"},
        {"title": "【学生課】健康診断再検査対象者の抽出と通知", "description": "二次健診の対象者名簿を作成し、各学科へ連絡してください。", "dept": "学生課", "priority": "中"},
        {"title": "【国際交流課】入国管理局 定期報告書類の集約", "description": "在籍状況・資格外活動状況の月次統計を取りまとめてください。", "dept": "国際交流課", "priority": "高"},
        {"title": "【就職指導課】秋季合同企業説明会のブース割り調整", "description": "参加確定企業20社のブースレイアウト案を策定してください。", "dept": "就職指導課", "priority": "中"},
        {"title": "【総務課】学納金延納・分納申請の審査確認", "description": "申請書類の確認と教務・学生課との情報照合を行ってください。", "dept": "総務課", "priority": "高"},
    ],
    "STAFF_USER": [
        {"title": "【引継ぎ】JLPT模擬試験の監督シフト調整", "description": "教職員の監督割当表のドラフトを作成してください。", "dept": "教務課", "priority": "高"},
        {"title": "【相談】学業不振・出席率低下学生へのヒアリング依頼", "description": "出席率が80%を切っている学生への個別面談を行ってください。", "dept": "学生課", "priority": "高"},
        {"title": "【書類照会】在留期間更新許可申請書の事前チェック", "description": "提出された所属機関等作成用シートの記載内容を確認してください。", "dept": "国際交流課", "priority": "高"},
        {"title": "【就職支援】IT企業向けポートフォリオ添削の担当振分", "description": "希望学生のGitHub/ポートフォリオ確認をお願いします。", "dept": "就職指導課", "priority": "中"},
        {"title": "【施設管理】PC演習室の空調・備品定期点検", "description": "次週の機材更新に伴う事前チェックをお願いします。", "dept": "総務課", "priority": "低"},
    ],
    "STUDENT_SINGLE": [
        {"title": "日本語能力試験（JLPT）受験票コピー提出", "description": "次回JLPTの受験票が届き次第、A4用紙にコピーして窓口へ提出してください。", "dept": "教務課", "priority": "高"},
        {"title": "Python3エンジニア認定基礎試験 模擬テスト受験確認", "description": "模擬試験アプリにて合格ライン（70%以上）を達成した結果画面を提出してください。", "dept": "教務課", "priority": "中"},
        {"title": "健康診断問診票および受診証明書の提出", "description": "未受診または証明書未提出の学生は、速やかに受診証明書を提出してください。", "dept": "学生課", "priority": "中"},
        {"title": "資格外活動許可書（アルバイト届）の提出", "description": "アルバイトを開始・更新する際は、許可証シールのコピーと就労条件書を提出してください。", "dept": "国際交流課", "priority": "高"},
        {"title": "在留期間更新許可申請に伴う所属機関作成書類の受領", "description": "出入国在留管理局へ提出する学校作成書類一式を発行・確認します。", "dept": "国際交流課", "priority": "高"},
        {"title": "就職活動：履歴書・エントリーシート添削", "description": "応募希望企業のES初稿を作成し、就職担当窓口で添削指導を受けてください。", "dept": "就職指導課", "priority": "高"},
        {"title": "住所・連絡先・緊急連絡先変更届の提出", "description": "引っ越しや電話番号変更があった場合は、在留カード両面の写しを添えて届け出てください。", "dept": "学生課", "priority": "高"},
    ],
    "STUDENT_MULTI": [
        {"title": "【クラス一括】前期中間プログラミング演習課題提出", "description": "指定リポジトリへコードをプッシュし、プルリクエストURLを報告してください。", "dept": "教務課", "priority": "高"},
        {"title": "【グループ提出】Unityゲーム制作チーム中間成果物ビルド提出", "description": "プロジェクト実行ファイル（Build）および仕様書を提出してください。", "dept": "教務課", "priority": "低"},
        {"title": "【学年共通】後期学納金納入案内書の受領確認", "description": "窓口にて納入案内書を受け取り、期日を確認してください。", "dept": "総務課", "priority": "高"},
        {"title": "【留学生一括】法務省告示に基づくパスポート・在留カード定期点検", "description": "原本を持参の上、指定日時に窓口で確認を受けてください。", "dept": "国際交流課", "priority": "高"},
        {"title": "【希望者対象】学内合同企業説明会 参加事前エントリー", "description": "参加希望の学生はエントリーシートを添えて期日までに申し込んでください。", "dept": "就職指導課", "priority": "中"},
    ]
}

def get_balanced_due_date(base_date):
    """
    期日超過・本日中・未来日をバランスよく生成する関数
    - 25%: 期日超過（1〜5日前） -> 【至急】枠
    - 25%: 本日中（当日）       -> 【至急】枠
    - 30%: 直近（1〜7日後）     -> 【今後の予定】枠
    - 20%: 先（8〜30日後）      -> 【今後の予定】枠
    """
    r = random.random()
    if r < 0.25:
        return base_date - timedelta(days=random.randint(1, 5))
    elif r < 0.50:
        return base_date
    elif r < 0.80:
        return base_date + timedelta(days=random.randint(1, 7))
    else:
        return base_date + timedelta(days=random.randint(8, 30))

def main():
    # 1. 教職員ユーザーの取得（5名）
    staffs = list(User.objects.filter(username__in=STAFF_USERNAMES))
    if len(staffs) < len(STAFF_USERNAMES):
        for uname in STAFF_USERNAMES:
            if not User.objects.filter(username=uname).exists():
                u = User.objects.create_user(username=uname, password="password123", is_staff=True)
                staffs.append(u)
    print(f"教職員5名: {[s.username for s in staffs]}")

    # 2. 部署（Group）の初期化
    dept_names = ["教務課", "学生課", "就職指導課", "国際交流課", "総務課"]
    group_map = {}
    for name in dept_names:
        group_obj, _ = Group.objects.get_or_create(name=name)
        group_map[name] = group_obj

    # 3. 学生データの取得
    students = list(Student.objects.all().order_by('id'))
    if not students:
        print("エラー: 学生データがありません。先に学生CSVを取り込んでください。")
        return
    print(f"対象学生数: {len(students)} 名")

    # ★ モデル定義から「未着手」の正しい内部キーを取得
    STATUS_TODO_KEY = get_choice_key(Task, 'status', '未着手')
    print(f"ステータス初期値キー: {STATUS_TODO_KEY}")

    today = date.today()
    print("タスク200件の生成を開始します...")

    # パターンの比率配分（合計200件）
    task_types = (
        ["GROUP"] * 30 +
        ["STAFF_USER"] * 30 +
        ["STUDENT_SINGLE"] * 100 +
        ["STUDENT_MULTI"] * 40
    )
    random.shuffle(task_types)

    student_cursor = 0
    created_count = 0

    for idx, t_type in enumerate(task_types):
        creator = staffs[idx % len(staffs)]
        tpl = random.choice(TEMPLATES[t_type])
        target_group_obj = group_map[tpl["dept"]]

        due = get_balanced_due_date(today)
        
        # ★ 優先度（高・中・低）の正しい内部キーを取得
        priority_key = get_choice_key(Task, 'priority', tpl["priority"])

        task_data = {
            "title": tpl["title"],
            "description": tpl["description"],
            "created_by": creator,
            "target_group": target_group_obj,
            "priority": priority_key,
            "due_date": due,
        }

        # 抽出した正しいステータスキーをセット
        if hasattr(Task, 'status'):
            task_data["status"] = STATUS_TODO_KEY

        if t_type == "GROUP":
            task_data["target_type"] = "GROUP"
            task = Task.objects.create(**task_data)

        elif t_type == "STAFF_USER":
            assigned_staff = staffs[(idx + 1) % len(staffs)]
            task_data["target_type"] = "USER"
            if hasattr(Task, 'assigned_user'):
                task_data["assigned_user"] = assigned_staff
            if hasattr(Task, 'target_user'):
                task_data["target_user"] = assigned_staff
            task = Task.objects.create(**task_data)

        elif t_type == "STUDENT_SINGLE":
            task_data["target_type"] = "STUDENT"
            task = Task.objects.create(**task_data)
            student = students[student_cursor % len(students)]
            student_cursor += 1
            task.students.add(student)

        elif t_type == "STUDENT_MULTI":
            task_data["target_type"] = "STUDENT"
            task = Task.objects.create(**task_data)
            batch_size = random.randint(2, 5)
            multi_students = [students[(student_cursor + i) % len(students)] for i in range(batch_size)]
            student_cursor += batch_size
            task.students.add(*multi_students)

        if hasattr(task, 'target_groups'):
            task.target_groups.add(target_group_obj)

        created_count += 1

    print(f"完了: 合計 {created_count} 件のタスクを生成しました！")

if __name__ == "__main__":
    main()