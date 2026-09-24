import unicodedata
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User, Group
from django.utils import timezone
from django.utils.safestring import mark_safe


def normalize_text(text):
    """半角カナを全角に、全角英数を半角に、全角スペースを半角スペースに変換"""
    if not text:
        return text
    # NFKC正規化（半角カナ→全角カナ、全角英数→半角英数など）
    normalized = unicodedata.normalize('NFKC', str(text))
    # 全角スペースを半角に変換
    return normalized.replace(' ', ' ').strip()

# --- 全世界国籍の選択肢リスト ---
# 1. 漢字表記の国名（先頭配置）
KANJI_COUNTRIES = [
    '日本', '韓国', '中国', '台湾', '香港',
]

# 2. カタカナ国名（五十音順）
KATAKANA_COUNTRIES = [
    # ア行
    'アイスランド', 'アイルランド', 'アゼルバイジャン', 'アフガニスタン', 'アメリカ',
    'アルジェリア', 'アルゼンチン', 'アルメニア', 'イギリス', 'イスラエル',
    'イタリア', 'イラク', 'イラン', 'インド', 'インドネシア',
    'ウガンダ', 'ウクライナ', 'ウズベキスタン', 'ウルグアイ', 'エジプト',
    'エストニア', 'エチオピア', 'オーストラリア', 'オーストリア', 'オマーン', 'オランダ',
    # カ行
    'ガーナ', 'カザフスタン', 'カタール', 'カナダ', 'カメルーン',
    'カンボジア', 'キルギス', 'ギリシャ', 'クウェート', 'クロアチア',
    'ケニア', 'コートジボワール', 'コスタリカ', 'コロンビア',
    # サ行
    'サウジアラビア', 'サモア', 'シンガポール', 'スイス', 'スウェーデン',
    'スペイン', 'スリランカ', 'スロバキア', 'セネガル', 'セルビア',
    # タ行
    'タイ', 'タジキスタン', 'タンザニア', 'チェコ', 'チュニジア',
    'チリ', 'デンマーク', 'ドイツ', 'ドミニカ共和国', 'トルクメニスタン',
    'トルコ', 'トンガ',
    # ナ行
    'ナイジェリア', 'ニュージーランド', 'ネパール', 'ノルウェー',
    # ハ行
    'バーレーン', 'パキスタン', 'パナマ', 'パプアニューギニア', 'パラオ',
    'パラグアイ', 'パレスチナ', 'ハンガリー', 'バングラデシュ', '東ティモール',
    'フィジー', 'フィリピン', 'フィンランド', 'フランス', 'ブラジル',
    'ブルガリア', 'ブルネイ', 'ベトナム', 'ベネズエラ', 'ベラルーシ',
    'ペルー', 'ベルギー', 'ポーランド', 'ボリビア', 'ポルトガル',
    # マ・ヤ・ラ行
    'マカオ', 'マダガスカル', 'マレーシア', '南アフリカ', 'ミャンマー',
    'メキシコ', 'モルディブ', 'モロッコ', 'モンゴル', 'ヨルダン',
    'ラオス', 'ラトビア', 'リトアニア', 'ルーマニア', 'レバノン', 'ロシア',
]

# 3. 最下部
BOTTOM_COUNTRIES = [
    '北朝鮮',
    'その他',
]

ALL_COUNTRIES = KANJI_COUNTRIES + KATAKANA_COUNTRIES + BOTTOM_COUNTRIES
NATIONALITY_CHOICES = [(c, c) for c in ALL_COUNTRIES]

class Student(models.Model):
    """学生基本情報"""
    student_id = models.CharField("学籍番号", max_length=20, unique=True)
    name = models.CharField("学生氏名", max_length=100)
    furigana = models.CharField("フリガナ", max_length=100, blank=True, null=True)
    nickname = models.CharField("ニックネーム", max_length=50, blank=True, null=True)
    nationality = models.CharField("国籍", max_length=50, choices=NATIONALITY_CHOICES, blank=True, null=True)
    
    # ▼ 文字列から外部キー（マスタ連携）へ変更 ▼
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="学科", related_name="students")
    course = models.ForeignKey('Course', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="コース", related_name="students")
    school_class = models.ForeignKey('SchoolClass', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="クラス", related_name="students")
    
    is_active = models.BooleanField("ステータス（表示）", default=True, db_index=True, help_text="チェックを外すとアプリの選択画面で非表示になります")
    created_at = models.DateTimeField("登録日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "学生"
        verbose_name_plural = "学生一覧"
        ordering = ['department__order', 'course__name', 'school_class__name', 'student_id']

    # 保存時の自動処理
    def save(self, *args, **kwargs):
        # 保存される瞬間に、氏名・フリガナ・ニックネームを強制的に正規化
        self.name = normalize_text(self.name)
        self.furigana = normalize_text(self.furigana)
        self.nickname = normalize_text(self.nickname)
        super().save(*args, **kwargs)

    def __str__(self):
        display_name = f"{self.name}（{self.nickname}）" if self.nickname else self.name
        dept_name = self.department.name if self.department else ""
        class_name = self.school_class.name if self.school_class else ""
        dept_info = f"[{dept_name} {class_name}]".strip()
        return f"{self.student_id} {display_name} {dept_info}".strip()

    @property
    def country_code(self):
        """国籍（全世界の国名・地域名・英語表記・コード）から2文字のISO国コード（小文字）を判定"""
        if not self.nationality:
            return ""
        val = self.nationality.strip()

        # 全世界の日本語国名・地域名マッピング（50音・地域順）
        mapping = {
            # --- アジア ---
            '日本': 'jp', '中国': 'cn', '台湾': 'tw', '韓国': 'kr', '大韓民国': 'kr',
            '香港': 'hk', 'マカオ': 'mo', 'モンゴル': 'mn', '北朝鮮': 'kp',
            'ベトナム': 'vn', 'タイ': 'th', 'ミャンマー': 'mm', 'インドネシア': 'id',
            'フィリピン': 'ph', 'マレーシア': 'my', 'シンガポール': 'sg', 'カンボジア': 'kh',
            'ラオス': 'la', 'ブルネイ': 'bn', '東ティモール': 'tl',
            'ネパール': 'np', 'スリランカ': 'lk', 'インド': 'in', 'バングラデシュ': 'bd',
            'パキスタン': 'pk', 'モルディブ': 'mv', 'ブータン': 'bt', 'アフガニスタン': 'af',
            'ウズベキスタン': 'uz', 'カザフスタン': 'kz', 'キルギス': 'kg',
            'タジキスタン': 'tj', 'トルクメニスタン': 'tm',

            # --- 中東・コーカサス ---
            'アゼルバイジャン': 'az', 'アルメニア': 'am', 'ジョージア': 'ge',
            'トルコ': 'tr', 'イラン': 'ir', 'イラク': 'iq', 'シリア': 'sy',
            'レバノン': 'lb', 'イスラエル': 'il', 'パレスチナ': 'ps', 'ヨルダン': 'jo',
            'サウジアラビア': 'sa', 'UAE': 'ae', 'アラブ首長国連邦': 'ae', 'カタール': 'qa',
            'クウェート': 'kw', 'オマーン': 'om', 'イエメン': 'ye', 'バーレーン': 'bh',

            # --- ヨーロッパ ---
            'イギリス': 'gb', '英国': 'gb', 'フランス': 'fr', 'ドイツ': 'de',
            'イタリア': 'it', 'スペイン': 'es', 'ポルトガル': 'pt', 'オランダ': 'nl',
            'ベルギー': 'be', 'スイス': 'ch', 'オーストリア': 'at', 'アイルランド': 'ie',
            'ギリシャ': 'gr', 'ロシア': 'ru', 'ウクライナ': 'ua', 'ベラルーシ': 'by',
            'ポーランド': 'pl', 'チェコ': 'cz', 'スロバキア': 'sk', 'ハンガリー': 'hu',
            'ルーマニア': 'ro', 'ブルガリア': 'bg', 'セルビア': 'rs', 'クロアチア': 'hr',
            'スウェーデン': 'se', 'ノルウェー': 'no', 'フィンランド': 'fi', 'デンマーク': 'dk',
            'アイスランド': 'is', 'エストニア': 'ee', 'ラトビア': 'lv', 'リトアニア': 'lt',

            # --- 北米・中南米 ---
            'アメリカ': 'us', '米国': 'us', 'アメリカ合衆国': 'us', 'カナダ': 'ca',
            'メキシコ': 'mx', 'ブラジル': 'br', 'アルゼンチン': 'ar', 'チリ': 'cl',
            'コロンビア': 'co', 'ペルー': 'pe', 'ベネズエラ': 've', 'ボリビア': 'bo',
            'パラグアイ': 'py', 'ウルグアイ': 'uy', 'エクアドル': 'ec', 'キューバ': 'cu',
            'ジャマイカ': 'jm', 'ドミニカ共和国': 'do', 'パナマ': 'pa', 'コスタリカ': 'cr',

            # --- オセアニア ---
            'オーストラリア': 'au', '豪州': 'au', 'ニュージーランド': 'nz', 'フィジー': 'fj',
            'パプアニューギニア': 'pg', 'サモア': 'ws', 'トンガ': 'to', 'パラオ': 'pw',

            # --- アフリカ ---
            'エジプト': 'eg', '南アフリカ': 'za', 'ナイジェリア': 'ng', 'ガーナ': 'gh',
            'ケニア': 'ke', 'エチオピア': 'et', 'タンザニア': 'tz', 'ウガンダ': 'ug',
            'モロッコ': 'ma', 'アルジェリア': 'dz', 'チュニジア': 'tn', 'セネガル': 'sn',
            'カメルーン': 'cm', 'コートジボワール': 'ci', 'マダガスカル': 'mg',
        }

        # 1. 完全一致判定
        if val in mapping:
            return mapping[val]

        # 2. 部分一致判定（例:「アゼルバイジャン共和国」など）
        for k, v in mapping.items():
            if k in val or val in k:
                return v

        # 3. 半角英字2文字（直接コード入力されている場合: az, jp など）
        if len(val) == 2 and val.isascii() and val.isalpha():
            return val.lower()

        return ""

    @property
    def flag_tag(self):
        """ローカル静的ファイル（/static/core/flags/xx.svg）から国旗を表示"""
        code = self.country_code
        if code:
            return (
                f'<img src="/static/core/flags/{code}.svg" '
                f'width="20" height="15" alt="{self.nationality}" '
                f'style="vertical-align: -2px; margin: 0 4px; border: 1px solid #ced4da; '
                f'border-radius: 2px; object-fit: cover; display: inline-block; flex-shrink: 0;">'
            )
        if self.nationality:
            return f'<span class="badge bg-light text-secondary border small mx-1" style="font-size:0.7rem; vertical-align: 1px;">{self.nationality}</span>'
        return ""

    @property
    def modal_display(self):
        """起票モーダル用表示"""
        sub_name = self.nickname if self.nickname else (self.furigana or '')
        sub_part = f" {sub_name}" if sub_name else ""
        flag_part = f" {self.flag_tag}" if self.flag_tag else ""
        
        dept_name = self.department.name if self.department else ""
        class_name = self.school_class.name if self.school_class else ""
        
        dept_part = f" {dept_name}" if dept_name else ""
        class_part = f" {class_name}" if class_name else ""

        return f"{self.name}{sub_part} ({self.student_id}){flag_part}{dept_part}{class_part}".strip()


class DepartmentGroup(Group):
    """管理画面メニュー用の所属部署プロキシモデル"""
    class Meta:
        proxy = True
        verbose_name = "所属部署"
        verbose_name_plural = "所属部署一覧"


class StaffDuty(models.Model):
    """担当業務マスタ"""
    department_group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='duties', verbose_name="所属部・課")
    name = models.CharField("担当業務名", max_length=100)

    class Meta:
        verbose_name = "担当業務"
        verbose_name_plural = "担当業務"
        unique_together = ('department_group', 'name')

    def __str__(self):
        return f"{self.department_group.name} - {self.name}"


class StaffProfile(models.Model):
    """教職員プロファイル"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile', verbose_name="教職員アカウント")
    department_group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="主所属（部・課）")
    duties = models.ManyToManyField(StaffDuty, blank=True, verbose_name="担当業務（複数選択可）")
    is_on_leave = models.BooleanField("休暇中", default=False)

    class Meta:
        verbose_name = "教職員プロファイル"
        verbose_name_plural = "教職員プロファイル一覧"

    def __str__(self):
        duties_str = " / ".join([d.name for d in self.duties.all()])
        # 主所属だけでなく、ユーザーが持つ「すべてのグループ」を抽出して表示
        depts = [g.name for g in self.user.groups.all()]
        dept_str = "、".join(depts) if depts else "無所属"
        
        return f"{self.user.last_name} {self.user.first_name}（{dept_str}：{duties_str}）"


class Task(models.Model):
    PRIORITY_CHOICES = [
        ('high', '高'),
        ('mid', '中'),
        ('low', '低'),
    ]
    STATUS_CHOICES = [
        ('open', '未対応'),
        ('in_progress', '対応中'),
        ('closed', '完了'),
    ]
    PRIVACY_CHOICES = [
        ('general', '一般（学内共有可）'),
        ('sensitive', '機密（関係部署のみ）'),
    ]
    TARGET_TYPE_CHOICES = [
        ('student', '学生'),
        ('staff', '教職員'),
    ]

    target_type = models.CharField("対象種別", max_length=10, choices=TARGET_TYPE_CHOICES, default='student', db_index=True)
    
    # 複数学生を1件にまとめて紐付ける ManyToManyField
    students = models.ManyToManyField(
        Student, 
        related_name='tasks', 
        verbose_name="対象学生",
        blank=True
    )
    
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='targeted_tasks',
        verbose_name="対象教職員",
        null=True,
        blank=True
    )
    target_users = models.ManyToManyField(
        User,
        related_name='targeted_tasks_m2m',
        verbose_name="対象教職員（複数）",
        blank=True
    )

    title = models.CharField("依頼件名", max_length=200)
    description = models.TextField("依頼内容")
    
    target_group = models.ForeignKey(
        Group, 
        on_delete=models.CASCADE, 
        verbose_name="担当部署", 
        related_name='group_tasks',
        null=True,
        blank=True
    )
    target_groups = models.ManyToManyField(
        Group,
        related_name='group_tasks_m2m',
        verbose_name="担当部署（複数）",
        blank=True
    )
    assigned_user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="個別担当者", 
        related_name='assigned_tasks'
    )
    
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='created_tasks', 
        verbose_name="起票者"
    )
    priority = models.CharField("優先度", max_length=10, choices=PRIORITY_CHOICES, default='mid', db_index=True)
    status = models.CharField("ステータス", max_length=20, choices=STATUS_CHOICES, default='open', db_index=True)
    privacy = models.CharField("プライバシー区分", max_length=20, choices=PRIVACY_CHOICES, default='general')
    
    due_date = models.DateField("対応期日", db_index=True)
    completion_note = models.TextField("対応メモ（クローズ時）", blank=True, null=True)
    
    is_archived = models.BooleanField("アーカイブ済み", default=False, db_index=True)
    reward_granted = models.BooleanField("報酬付与済み", default=False)

    created_at = models.DateTimeField("起票日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "タスク"
        verbose_name_plural = "タスク一覧"
        ordering = ['due_date', '-priority']

    def __str__(self):
        return f"[{self.get_priority_display()}] {self.title}"

    @property
    def is_urgent(self):
        """当日期限または期日超過かつ未完了か判定"""
        return self.status != 'closed' and self.due_date <= timezone.now().date()

    @property
    def target_groups_display(self):
        """担当部署の一覧表示（複数対応）"""
        groups = list(self.target_groups.all())
        if groups:
            return "、".join([g.name for g in groups])
        elif self.target_group:
            return self.target_group.name
        return "部署指定なし"

    @property
    def target_display(self):
        """一覧画面用の対象者表示（単数・複数学生まとめ・教職員対応）"""
        if self.target_type == 'student':
            student_list = list(self.students.all())
            if not student_list:
                return mark_safe('<span class="text-muted">学生指定なし</span>')

            first_st = student_list[0]
            dept_name = first_st.department.name if first_st.department else ""
            cls_name = first_st.school_class.name if first_st.school_class else ""
            dept_part = f"{dept_name} {cls_name}".strip()
            line1 = f'<div class="text-secondary small mb-1" style="font-size: 0.78rem; line-height: 1.2;">{dept_part}</div>' if dept_part else ''

            if len(student_list) == 1:
                line2 = f'<div class="fw-bold text-dark" style="font-size: 0.95rem;">{first_st.name} <span class="text-secondary fw-normal small">({first_st.student_id})</span></div>'
                if first_st.nickname:
                    line3 = f'<div class="mt-1"><span class="badge rounded-pill bg-light text-secondary border" style="font-size: 0.75rem;">🏷️ {first_st.nickname}</span></div>'
                elif first_st.furigana:
                    line3 = f'<div class="text-secondary small mt-1" style="font-size: 0.75rem;">{first_st.furigana}</div>'
                else:
                    line3 = ''
                return mark_safe(f'{line1}{line2}{line3}')
            else:
                names_tooltip = ", ".join([f"{s.name}({s.student_id})" for s in student_list])
                line2 = f'''<div class="fw-bold text-dark" style="font-size: 0.95rem;">{first_st.name} <span class="badge bg-primary ms-1" data-bs-toggle="tooltip" data-bs-title="{names_tooltip}" style="cursor: pointer;">他 {len(student_list) - 1} 名</span></div>'''
                line3 = f'<div class="text-muted small mt-1" style="font-size: 0.75rem;">計 {len(student_list)} 名の一括案件</div>'
                return mark_safe(f'{line1}{line2}{line3}')

        elif self.target_type == 'staff':
            target_user_list = list(self.target_users.all())
            if not target_user_list and self.target_user:
                target_user_list = [self.target_user]

            if target_user_list:
                first_u = target_user_list[0]
                first_u_name = f"{first_u.last_name} {first_u.first_name}".strip() or first_u.username
                if len(target_user_list) == 1:
                    return mark_safe(f'<div class="fw-bold text-dark">{first_u_name}</div><span class="badge bg-secondary" style="font-size: 0.75rem;">教職員宛て</span>')
                else:
                    names_tooltip = ", ".join([f"{u.last_name} {u.first_name}".strip() or u.username for u in target_user_list])
                    line1 = f'<div class="fw-bold text-dark">{first_u_name} <span class="badge bg-primary ms-1" data-bs-toggle="tooltip" data-bs-title="{names_tooltip}" style="cursor: pointer;">他 {len(target_user_list) - 1} 名</span></div>'
                    line2 = f'<span class="badge bg-secondary" style="font-size: 0.75rem;">教職員宛て (計 {len(target_user_list)} 名)</span>'
                    return mark_safe(f'{line1}{line2}')

            target_group_list = list(self.target_groups.all())
            if not target_group_list and self.target_group:
                target_group_list = [self.target_group]

            if target_group_list:
                first_g = target_group_list[0]
                if len(target_group_list) == 1:
                    return mark_safe(f'<div class="fw-bold text-dark">{first_g.name}</div><span class="badge bg-secondary" style="font-size: 0.75rem;">部署宛て</span>')
                else:
                    groups_tooltip = ", ".join([g.name for g in target_group_list])
                    line1 = f'<div class="fw-bold text-dark">{first_g.name} <span class="badge bg-primary ms-1" data-bs-toggle="tooltip" data-bs-title="{groups_tooltip}" style="cursor: pointer;">他 {len(target_group_list) - 1} 部署</span></div>'
                    line2 = f'<span class="badge bg-secondary" style="font-size: 0.75rem;">部署宛て (計 {len(target_group_list)} 部署)</span>'
                    return mark_safe(f'{line1}{line2}')

            return mark_safe('<span class="badge bg-secondary" style="font-size: 0.75rem;">部署宛て</span>')
        else:
            return mark_safe('<span class="badge bg-secondary" style="font-size: 0.75rem;">部署宛て</span>')


class TaskComment(models.Model):
    """申し送り・対応履歴ログ"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments', verbose_name="対象タスク")
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="記入者")
    content = models.TextField("申し送り内容・メモ")
    created_at = models.DateTimeField("記入日時", auto_now_add=True)

    class Meta:
        verbose_name = "対応メモ"
        verbose_name_plural = "対応メモ履歴"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.task.title} - {self.author.username} ({self.created_at:%m/%d %H:%M})"


class TaskStudentProgress(models.Model):
    """複数学生タスクにおける学生個別の対応進捗とメモ"""
    STATUS_CHOICES = [
        ('open', '未対応'),
        ('in_progress', '対応中'),
        ('closed', '完了'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='student_progresses', verbose_name="対象タスク")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='task_progresses', verbose_name="対象学生")
    status = models.CharField("ステータス", max_length=20, choices=STATUS_CHOICES, default='open')
    memo = models.CharField("個別メモ・進捗", max_length=255, blank=True, null=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "学生別進捗"
        verbose_name_plural = "学生別進捗一覧"
        unique_together = ('task', 'student')

    def __str__(self):
        return f"{self.task.title} - {self.student.name} ({self.get_status_display()})"

class Department(models.Model):
    """学科マスタ"""
    name = models.CharField("学科名", max_length=100, unique=True)
    order = models.PositiveIntegerField("表示順", default=0, help_text="数字が小さい順に並びます")

    class Meta:
        verbose_name = "学科"
        verbose_name_plural = "学科一覧"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

class Course(models.Model):
    """コースマスタ（学科に紐付け）"""
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses', verbose_name="所属学科")
    name = models.CharField("コース名", max_length=100)

    class Meta:
        verbose_name = "コース"
        verbose_name_plural = "コース一覧"
        ordering = ['department__order', 'department__name', 'name']
        unique_together = ('department', 'name')

    def __str__(self):
        return self.name

class SchoolClass(models.Model):
    """クラスマスタ（学科とコースに紐付け）"""
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='classes', verbose_name="所属学科")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='classes', verbose_name="所属コース", null=True, blank=True)
    name = models.CharField("クラス名", max_length=50, help_text="例: HT-A, IT-Bなど")

    class Meta:
        verbose_name = "クラス"
        verbose_name_plural = "クラス一覧"
        ordering = ['department__order', 'course__name', 'name']
        unique_together = ('department', 'course', 'name')

    def __str__(self):
        course_info = f"（{self.course.name}）" if self.course else ""
        return f"{self.department.name}{course_info} {self.name}"  

# --- ユーザーと教職員プロファイルの自動同期 ---
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth.models import User

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """ユーザーが新規作成された際、自動で教職員プロファイルを作成"""
    if instance.is_staff:
        StaffProfile.objects.get_or_create(user=instance)

@receiver(m2m_changed, sender=User.groups.through)
def sync_user_department(sender, instance, action, **kwargs):
    """ユーザーの所属グループ（部署）が変更された際、自動でプロファイルの主所属に同期"""
    if action in ["post_add", "post_remove", "post_clear"]:
        if instance.is_staff:
            profile, _ = StaffProfile.objects.get_or_create(user=instance)
            profile.department_group = instance.groups.first()  # 最初のグループを主所属とする
            profile.save()

# --- 教職員(User)モデル保存時の自動正規化 ---
@receiver(pre_save, sender=User)
def normalize_user_fields(sender, instance, **kwargs):
    if instance.username:
        # ユーザー名はスペース自体を除去
        instance.username = unicodedata.normalize('NFKC', instance.username).replace(' ', '').replace(' ', '')
    if instance.last_name:
        instance.last_name = normalize_text(instance.last_name)
    if instance.first_name:
        instance.first_name = normalize_text(instance.first_name)


class UserCompanion(models.Model):
    COMPANION_CHOICES = [
        ('none', '未選択'),
        ('chick', 'ひよこ'),
        ('robot', 'ロボット'),
        ('cactus', 'サボテン'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='usercompanion', verbose_name="ユーザー")
    companion_type = models.CharField("キャラクター種類", max_length=20, choices=COMPANION_CHOICES, default='none')
    completed_tasks_count = models.IntegerField("完了タスク数", default=0)

    class Meta:
        verbose_name = "育成キャラクター"
        verbose_name_plural = "育成キャラクター一覧"

    @property
    def level(self):
        if self.completed_tasks_count < 3:
            return 1
        elif self.completed_tasks_count < 10:
            return 2
        elif self.completed_tasks_count < 25:
            return 3
        else:
            return 4

    @property
    def current_form(self):
        forms = {
            'chick': {1: '🐣', 2: '🐥', 3: '🐓', 4: '🦅'},
            'robot': {1: '🤖(💤)', 2: '🤖(⚡)', 3: '🦾', 4: '🦸‍♂️'},
            'cactus': {1: '🌱', 2: '🌿', 3: '🌳', 4: '🌸'},
        }
        if self.companion_type == 'none' or self.companion_type not in forms:
            return '❓'
        return forms[self.companion_type][self.level]

    @property
    def progress_to_next_level(self):
        if self.level == 1:
            return int((self.completed_tasks_count / 3) * 100)
        elif self.level == 2:
            return int(((self.completed_tasks_count - 3) / 7) * 100)
        elif self.level == 3:
            return int(((self.completed_tasks_count - 10) / 15) * 100)
        else:
            return 100

@receiver(post_save, sender=User)
def create_user_companion(sender, instance, created, **kwargs):
    if created:
        UserCompanion.objects.get_or_create(user=instance)


class Achievement(models.Model):
    CATEGORY_CHOICES = [
        ('TASK_COUNT', 'タスク件数'),
        ('STREAK', '継続日数'),
        ('ISLAND_LEVEL', '島レベル'),
        ('GACHA', 'ガチャ回数'),
        ('OTHER', 'その他'),
    ]

    code = models.CharField("実績コード", max_length=50, unique=True)
    name = models.CharField("実績名 / 称号名", max_length=100)
    description = models.TextField("説明", blank=True, null=True)
    category = models.CharField("カテゴリ", max_length=30, choices=CATEGORY_CHOICES, default='TASK_COUNT')
    requirement_value = models.IntegerField("達成必要値", default=1)
    created_at = models.DateTimeField("登録日時", auto_now_add=True)

    class Meta:
        verbose_name = "実績・称号"
        verbose_name_plural = "実績・称号一覧"
        ordering = ['category', 'requirement_value', 'created_at']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.name} ({self.code})"


class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_achievements', verbose_name="ユーザー")
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name='user_achievements', verbose_name="実績")
    achieved_at = models.DateTimeField("達成日時", auto_now_add=True)

    class Meta:
        verbose_name = "ユーザー獲得実績"
        verbose_name_plural = "ユーザー獲得実績一覧"
        ordering = ['-achieved_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'achievement'], name='unique_user_achievement')
        ]

    def __str__(self):
        return f"{self.user.username} - {self.achievement.name}"


class UserTaskCompletionDate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_completion_dates', verbose_name="ユーザー")
    date = models.DateField("タスク完了日", db_index=True)

    class Meta:
        verbose_name = "ユーザー日別タスク完了記録"
        verbose_name_plural = "ユーザー日別タスク完了記録一覧"
        constraints = [
            models.UniqueConstraint(fields=['user', 'date'], name='unique_user_completion_date')
        ]

    def __str__(self):
        return f"{self.user.username} - {self.date}"


class IslandProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='island_profile', verbose_name="ユーザー")
    level = models.IntegerField("島レベル", default=1)
    experience = models.IntegerField("島経験値", default=0)
    coins = models.IntegerField("コイン", default=0)
    gacha_tickets = models.IntegerField("ガチャチケット", default=0)
    current_title = models.ForeignKey(Achievement, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name="現在の称号")
    created_at = models.DateTimeField("登録日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "マイアイランド情報"
        verbose_name_plural = "マイアイランド情報一覧"

    def __str__(self):
        return f"{self.user.username} - Island Lv.{self.level} (EXP: {self.experience})"

    @property
    def next_level_exp(self):
        thresholds = {1: 50, 2: 120, 3: 220, 4: 350}
        return thresholds.get(self.level, 350)

    @property
    def current_level_base_exp(self):
        bases = {1: 0, 2: 50, 3: 120, 4: 220, 5: 350}
        return bases.get(self.level, 350)

    @property
    def exp_progress_percent(self):
        if self.level >= 5:
            return 100
        base = self.current_level_base_exp
        target = self.next_level_exp
        needed = target - base
        current = self.experience - base
        if needed <= 0:
            return 100
        progress = int((current / needed) * 100)
        return max(0, min(100, progress))

    def update_level(self):
        """EXPに応じてレベルを更新し、レベル上昇があった場合は(True, old_level, new_level)を返す"""
        old_level = self.level
        exp = self.experience
        if exp >= 350:
            new_level = 5
        elif exp >= 220:
            new_level = 4
        elif exp >= 120:
            new_level = 3
        elif exp >= 50:
            new_level = 2
        else:
            new_level = 1

        if new_level > old_level:
            self.level = new_level
            return True, old_level, new_level
        return False, old_level, new_level


@receiver(post_save, sender=User)
def create_island_profile(sender, instance, created, **kwargs):
    if created:
        IslandProfile.objects.get_or_create(user=instance)


class IslandItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('tree', '樹木 🌲'),
        ('flower', 'お花 🌸'),
        ('rock', '大きな岩 🪨'),
        ('house', '小さな家 🏠'),
        ('fountain', '噴水 ⛲'),
        ('shop', 'お店 🏪'),
        ('animal', '動物 🐶'),
        ('castle', 'お城 🏰'),
    ]

    ITEM_ICONS = {
        'tree': '🌲',
        'flower': '🌸',
        'rock': '🪨',
        'house': '🏠',
        'fountain': '⛲',
        'shop': '🏪',
        'animal': '🐶',
        'castle': '🏰',
    }

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='island_items', verbose_name="ユーザー")
    item_type = models.CharField("アイテム種類", max_length=50, choices=ITEM_TYPE_CHOICES)
    name = models.CharField("アイテム名", max_length=100)
    position_x = models.IntegerField("配置位置X", default=0, null=True, blank=True)
    position_y = models.IntegerField("配置位置Y", default=0, null=True, blank=True)
    obtained_at = models.DateTimeField("獲得日時", auto_now_add=True)
    is_placed = models.BooleanField("配置済み", default=True)

    class Meta:
        verbose_name = "島アイテム"
        verbose_name_plural = "島アイテム一覧"
        ordering = ['-obtained_at']

    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.get_item_type_display()})"

    @property
    def icon(self):
        return self.ITEM_ICONS.get(self.item_type, '🎁')


class GraduatedCompanion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='graduated_companions', verbose_name="ユーザー")
    companion_type = models.CharField("キャラクター種類", max_length=20, choices=UserCompanion.COMPANION_CHOICES)
    completed_tasks_count = models.IntegerField("卒業時完了タスク数", default=0)
    graduated_at = models.DateTimeField("殿堂入り日時", auto_now_add=True)

    class Meta:
        verbose_name = "殿堂入りキャラクター"
        verbose_name_plural = "殿堂入りキャラクター一覧"
        ordering = ['-graduated_at']

    def __str__(self):
        return f"{self.user.username} - {self.get_companion_type_display()} ({self.graduated_at:%Y/%m/%d})"

    @property
    def final_form(self):
        forms = {
            'chick': '🦅',
            'robot': '🦸‍♂️',
            'cactus': '🌸',
        }
        return forms.get(self.companion_type, '❓')
