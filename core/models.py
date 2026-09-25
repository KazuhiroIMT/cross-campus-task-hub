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
        ('medium', '中'),
        ('low', '低'),
    ]
    STATUS_CHOICES = [
        ('open', '未着手'),
        ('todo', '未着手'),
        ('in_progress', '対応中'),
        ('closed', '完了'),
        ('completed', '完了'),
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
        ('open', '未着手'),
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
        # 動物系 (15種)
        ('shiba_inu', 'シバイヌ 🐕'),
        ('calico_cat', '三毛猫 🐈'),
        ('rabbit', 'ウサギ 🐇'),
        ('squirrel', 'リス 🐿️'),
        ('owl', 'フクロウ 🦉'),
        ('fox', 'キツネ 🦊'),
        ('lesser_panda', 'レッサーパンダ 🐼'),
        ('penguin', 'ペンギン 🐧'),
        ('otter', 'カワウソ 🦦'),
        ('fennec', 'フェネック 🦊'),
        ('koala', 'コアラ 🐨'),
        ('hedgehog', 'ハリネズミ 🦔'),
        ('fawn', '子ジカ 🦌'),
        ('seal', 'アザラシ 🦭'),
        ('white_tiger', '白トラ 🐅'),
        # 植物・精霊系 (15種)
        ('mandragora', 'マンドラゴラ 🪴'),
        ('cactus_boy', 'サボテン坊や 🌵'),
        ('sunflower_spirit', 'ヒマワリ精霊 🌻'),
        ('acorn_boy', 'ドングリ小僧 🌰'),
        ('mushroom_fairy', 'きのこ妖精 🍄'),
        ('cherry_spirit', '桜の精霊 🌸'),
        ('clover_spirit', '四つ葉のクローバー 🍀'),
        ('moss_ball', 'コケ丸 🟢'),
        ('lotus_spirit', '蓮の花の精 🪷'),
        ('ivy_runner', 'ツタランナー 🌿'),
        ('rose_fairy', 'ローズフェアリー 🌹'),
        ('tree_elder', '樹木長老 🌳'),
        ('palm_spirit', 'ヤシの精 🌴'),
        ('succulent', '多肉ちゃん 🪴'),
        ('apple_fairy', 'リンゴの妖精 🍎'),
        # 旧互換キー
        ('chick', 'ひよこ 🐣'),
        ('robot', 'ロボット 🤖'),
        ('cactus', 'サボテン 🌱'),
    ]

    COMPANION_FORMS = {
        'shiba_inu': {1: '🐾', 2: '🐕‍🦺', 3: '🐕', 4: '🐕', 5: '🐕✨', 6: '🐕‍🦺🌟', 7: '🐕⚡', 8: '🐕🔥', 9: '🐕🌈', 10: '神狼シバイヌ 🐕‍🦺👑'},
        'calico_cat': {1: '🐾', 2: '🐈‍⬛', 3: '🐈', 4: '🐈', 5: '🐈✨', 6: '🐈‍⬛🌟', 7: '🐈⚡', 8: '🐈🔥', 9: '🐈🌈', 10: '霊猫ミケ 🐈‍⬛👑'},
        'rabbit': {1: '🥚', 2: '🐇', 3: '🐇', 4: '🐇✨', 5: '🐇🌟', 6: '🐇⚡', 7: '🐇🔥', 8: '🐇🌈', 9: '月兎 🐇🌙', 10: '月宮仙兎 🐇👑'},
        'squirrel': {1: '🌰', 2: '🐿️', 3: '🐿️', 4: '🐿️✨', 5: '🐿️🌟', 6: '🐿️⚡', 7: '🐿️🔥', 8: '🐿️🌈', 9: '疾風リス 🐿️💨', 10: '雷光風リス 🐿️👑'},
        'owl': {1: '🥚', 2: '🦉', 3: '🦉', 4: '🦉✨', 5: '🦉🌟', 6: '🦉⚡', 7: '🦉🔥', 8: '🦉🌈', 9: '賢者ミミズク 🦉📜', 10: '叡智の大天梟 🦉👑'},
        'fox': {1: '🐾', 2: '🦊', 3: '🦊', 4: '🦊✨', 5: '🦊🌟', 6: '🦊⚡', 7: '🦊🔥', 8: '九尾の狐 🦊🔥', 9: '天狐 🦊🌈', 10: '九尾仙狐 🦊👑'},
        'lesser_panda': {1: '🐾', 2: '🐼', 3: '🐼', 4: '🐼✨', 5: '🐼🌟', 6: '🐼⚡', 7: '🐼🔥', 8: 'レッサー武者 🐼⚔️', 9: '威風レッサー 🐼🌈', 10: '烈火レッサー王 🐼👑'},
        'penguin': {1: '🥚', 2: '🐧', 3: '🐧', 4: '🐧✨', 5: '🐧🌟', 6: '🐧⚡', 7: '氷結ペンギン 🐧❄️', 8: '皇帝ペンギン 🐧👑', 9: '極光ペンギン 🐧🌌', 10: '極寒帝ペンギン 🐧👑'},
        'otter': {1: '🐾', 2: '🦦', 3: '🦦', 4: '🦦✨', 5: '🦦🌟', 6: '🦦⚡', 7: '水流カワウソ 🦦💧', 8: '波導カワウソ 🦦🌊', 9: '海神カワウソ 🦦🔱', 10: '水龍霊カワウソ 🦦👑'},
        'fennec': {1: '🐾', 2: '🦊', 3: '🦊', 4: '🦊✨', 5: '砂漠フェネック 🦊🏜️', 6: '幻砂フェネック 🦊✨', 7: '風砂フェネック 🦊🌪️', 8: '太陽フェネック 🦊☀️', 9: '蜃気楼フェネック 🦊🌟', 10: '砂神フェネック 🦊👑'},
        'koala': {1: '🌱', 2: '🐨', 3: '🐨', 4: '🐨✨', 5: 'ユーカリコアラ 🐨🌿', 6: '安らぎコアラ 🐨💤', 7: '大樹コアラ 🐨🌳', 8: '守護者コアラ 🐨🛡️', 9: '森精コアラ 🐨🌈', 10: '世界樹コアラ王 🐨👑'},
        'hedgehog': {1: '🪨', 2: '🦔', 3: '🦔', 4: '🦔✨', 5: 'トゲトゲハリネズミ 🦔⚡', 6: '鋼鉄ハリネズミ 🦔🛡️', 7: '疾風ハリネズミ 🦔💨', 8: '閃光ハリネズミ 🦔✨', 9: '金剛ハリネズミ 🦔💎', 10: '針聖王ハリネズミ 🦔👑'},
        'fawn': {1: '🌱', 2: '🦌', 3: '🦌', 4: '🦌✨', 5: '若鹿 🦌🌿', 6: '草原の鹿 🦌🌾', 7: '神木鹿 🦌🌳', 8: '蒼天の角鹿 🦌✨', 9: '聖霊鹿 🦌🌟', 10: '森林神シカ 🦌👑'},
        'seal': {1: '🧊', 2: '🦭', 3: '🦭', 4: '🦭✨', 5: '氷原アザラシ 🦭❄️', 6: '流氷アザラシ 🦭🌊', 7: 'オーロラアザラシ 🦭🌌', 8: '蒼海アザラシ 🦭💎', 9: '氷晶アザラシ 🦭✨', 10: '海王精アザラシ 🦭👑'},
        'white_tiger': {1: '🐾', 2: '🐅', 3: '🐅', 4: '🐅✨', 5: '白虎幼獣 🐅⚡', 6: '迅雷の白トラ 🐅⚡', 7: '風雲の白トラ 🐅🌪️', 8: '白虎武神 🐅⚔️', 9: '四神白虎 🐅✨', 10: '天帝白虎 🐅👑'},

        'mandragora': {1: '🌱', 2: '🪴', 3: '🪴', 4: 'マンドラ 🪴✨', 5: '叫ぶマンドラ 🪴🎶', 6: '音撃マンドラ 🪴⚡', 7: '魔法マンドラ 🪴🪄', 8: '歌姫マンドラ 🪴🎤', 9: '大樹マンドラ 🪴🌳', 10: '世界樹のマンドラゴラ 🪴👑'},
        'cactus_boy': {1: '🌱', 2: '🌵', 3: '🌵', 4: 'サボテンくん 🌵✨', 5: 'トゲトゲサボテン 🌵⚡', 6: '情熱サボテン 🌵🔥', 7: '花開くサボテン 🌵🌸', 8: '砂漠の覇王サボテン 🌵👑', 9: '太陽サボテン 🌵☀️', 10: '陽光の神サボテン 🌵👑'},
        'sunflower_spirit': {1: '🌱', 2: '🌻', 3: '🌻', 4: 'ヒマワリちゃん 🌻✨', 5: '太陽ヒマワリ 🌻☀️', 6: '黄金ヒマワリ 🌻✨', 7: '大輪ヒマワリ 🌻🌟', 8: '日輪精霊 🌻🔥', 9: '天日精霊 🌻🌈', 10: '太陽神ヒマワリ 🌻👑'},
        'acorn_boy': {1: '🌰', 2: '🌰🌱', 3: 'ドングリぼうや 🌰✨', 4: 'ドングリ騎士 🌰⚔️', 5: '樫の木の精 🌰🌳', 6: '森の用心棒 🌰🛡️', 7: '木の実王 🌰👑', 8: '森の守護神 🌰🌟', 9: '世界樹の騎士 🌰⚔️', 10: '大樹聖騎士ドングリ 🌰👑'},
        'mushroom_fairy': {1: '🍄', 2: '🍄✨', 3: 'キノコちゃん 🍄🌟', 4: '毒キノコ妖精 🍄💜', 5: '光るキノコ 🍄💡', 6: '胞子ダンス 🍄💃', 7: '幻惑のキノコ 🍄✨', 8: '大妖精キノコ 🍄👑', 9: '菌界の女王 🍄👸', 10: '真菌神ドクキノコ 🍄👑'},
        'cherry_spirit': {1: '🌱', 2: '🌸', 3: '🌸', 4: '桜のつぼみ 🌸✨', 5: '桜花妖精 🌸💫', 6: '満開桜 🌸🌟', 7: '春風の桜精 🌸🍃', 8: '桜吹雪姫 🌸👑', 9: '千本桜精 🌸✨', 10: '桜神天女 🌸👑'},
        'clover_spirit': {1: '🌱', 2: '🍀', 3: '🍀', 4: '四つ葉ちゃん 🍀✨', 5: '幸運のクローバー 🍀🌟', 6: 'ラッキースピリット 🍀💫', 7: '黄金クローバー 🍀✨', 8: '祝福の妖精 🍀👼', 9: '奇跡のクローバー 🍀🌈', 10: '幸福神クローバー 🍀👑'},
        'moss_ball': {1: '🟢', 2: '🟢✨', 3: 'コケ丸 🟢', 4: 'コロコロコケ丸 🟢💨', 5: 'ふわふわモスコケ 🟢🌿', 6: '清流コケ丸 🟢💧', 7: '古代コケ丸 🟢🪨', 8: '大樹のコケ丸 🟢🌳', 9: '生命のコケ玉 🟢✨', 10: '森羅万象コケ神 🟢👑'},
        'lotus_spirit': {1: '🌱', 2: '🪷', 3: '🪷', 4: 'ハスの華 🪷✨', 5: '清らかな蓮 🪷💧', 6: '水上の蓮精 🪷🌊', 7: '浄化の蓮姫 🪷✨', 8: '聖なる蓮華 🪷🌟', 9: '天界の蓮華 🪷👼', 10: '極楽蓮華天女 🪷👑'},
        'ivy_runner': {1: '🌱', 2: '🌿', 3: '🌿', 4: 'ツタちゃん 🌿✨', 5: '疾走ツタランナー 🌿💨', 6: '緑のツタ騎士 🌿⚔️', 7: '碧緑ツタウィザード 🌿🪄', 8: '森の導き手 🌿🌟', 9: '大地を駆けるツタ 🌿⚡', 10: '大自然ツタ神 🌿👑'},
        'rose_fairy': {1: '🌱', 2: '🌹', 3: '🌹', 4: '薔薇の蕾 🌹✨', 5: 'ローズプリンセス 🌹👑', 6: '情熱の赤薔薇 🌹🔥', 7: '高貴な妖精 🌹💫', 8: '薔薇の女王 🌹👸', 9: '真紅の薔薇精 🌹✨', 10: '美と情熱の薔薇神 🌹👑'},
        'tree_elder': {1: '🌱', 2: '🌳', 3: '🌳', 4: '若い大樹 🌳✨', 5: '長老の芽 🌳🌿', 6: '智慧の大樹 🌳📜', 7: '森の長老 🌳👴', 8: '古代樹の精 🌳🌟', 9: '世界樹の長老 🌳🌌', 10: '全知全能の樹木神 🌳👑'},
        'palm_spirit': {1: '🌱', 2: '🌴', 3: '🌴', 4: '南国ヤシくん 🌴✨', 5: 'トロピカル精霊 🌴🍹', 6: 'ココナッツ精 🌴🥥', 7: '常夏の歌い手 🌴🎶', 8: '常夏王ヤシ 🌴👑', 9: '太陽と海ヤシ 🌴☀️', 10: '常夏楽園の神 🌴👑'},
        'succulent': {1: '🌱', 2: '🪴', 3: '🪴', 4: 'ぷにぷに多肉 🪴✨', 5: '宝石多肉 🪴💎', 6: 'オパール多肉 🪴🌟', 7: '癒やしの多肉 🪴💖', 8: '華麗なる多肉 🪴🌹', 9: '不滅の多肉精 🪴✨', 10: '永遠の翡翠多肉神 🪴👑'},
        'apple_fairy': {1: '🌱', 2: '🍎', 3: '🍎', 4: 'リンゴちゃん 🍎✨', 5: '完熟リンゴ妖精 🍎💫', 6: '甘美なリンゴ精 🍎🍯', 7: '黄金のリンゴ 🍎✨', 8: '知恵のリンゴ姫 🍎👸', 9: '楽園のリンゴ精 🍎🌈', 10: '禁断の果実アダム神 🍎👑'},

        'chick': {1: '🐣', 2: '🐥', 3: '🐥✨', 4: '🐓', 5: '🐓🔥', 6: '🦅', 7: '🦅⚡', 8: '🦅🔥', 9: '鳳凰 🦅🌈', 10: '不死鳥フェニックス 🦅👑'},
        'robot': {1: '🤖(💤)', 2: '🤖(⚡)', 3: '🤖', 4: '🦾', 5: '🦸‍♂️', 6: '🦸‍♂️⚡', 7: '🦸‍♂️🔥', 8: '超機甲神 🤖⚔️', 9: '銀河ロボ 🤖🌌', 10: '絶対神ロボ 🤖👑'},
        'cactus': {1: '🌱', 2: '🌿', 3: '🌵', 4: '🌵✨', 5: '🌳', 6: '🌸', 7: '🌸✨', 8: '🌸🔥', 9: '神木サボテン 🌵🌈', 10: 'サボテンの神 🌵👑'},
    }

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='usercompanion', verbose_name="ユーザー")
    companion_type = models.CharField("キャラクター種類", max_length=50, choices=COMPANION_CHOICES, default='none')
    completed_tasks_count = models.IntegerField("完了タスク数", default=0)

    class Meta:
        verbose_name = "育成キャラクター"
        verbose_name_plural = "育成キャラクター一覧"

    @property
    def level(self):
        cnt = self.completed_tasks_count
        if cnt < 2:
            return 1
        elif cnt < 4:
            return 2
        elif cnt < 7:
            return 3
        elif cnt < 11:
            return 4
        elif cnt < 16:
            return 5
        elif cnt < 22:
            return 6
        elif cnt < 29:
            return 7
        elif cnt < 37:
            return 8
        elif cnt < 46:
            return 9
        else:
            return 10

    @property
    def stage_name(self):
        lvl = self.level
        if lvl <= 3:
            return "幼体・種/芽"
        elif lvl <= 7:
            return "成長期"
        else:
            return "成体・覚醒形態"

    @property
    def current_form(self):
        if self.companion_type == 'none' or self.companion_type not in self.COMPANION_FORMS:
            return '❓'
        forms = self.COMPANION_FORMS[self.companion_type]
        return forms.get(self.level, forms.get(10, '❓'))

    @property
    def required_tasks_for_next_level(self):
        thresholds = {1: 2, 2: 4, 3: 7, 4: 11, 5: 16, 6: 22, 7: 29, 8: 37, 9: 46, 10: 46}
        return thresholds.get(self.level, 46)

    @property
    def current_level_base_tasks(self):
        bases = {1: 0, 2: 2, 3: 4, 4: 7, 5: 11, 6: 16, 7: 22, 8: 29, 9: 37, 10: 46}
        return bases.get(self.level, 0)

    @property
    def progress_to_next_level(self):
        if self.level >= 10:
            return 100
        base = self.current_level_base_tasks
        target = self.required_tasks_for_next_level
        needed = target - base
        current = self.completed_tasks_count - base
        if needed <= 0:
            return 100
        progress = int((current / needed) * 100)
        return max(0, min(100, progress))

    @property
    def trait_history(self):
        """到達レベルごとの習得特性・進化履歴"""
        history = []
        if self.companion_type == 'none':
            return history

        forms = self.COMPANION_FORMS.get(self.companion_type, {})
        lvl = self.level

        for l in range(1, lvl + 1):
            f = forms.get(l, '')
            if l == 1:
                desc = "誕生（幼体・種/芽）: 新しい命が目覚めました。"
            elif l == 4:
                desc = "進化（成長期）: 活発に成長し、固有のオーラを纏い始めました。"
            elif l == 8:
                desc = "覚醒（成体・覚醒形態）: 完全な姿へ進化し、強力な力を解放しました。"
            elif l == 10:
                desc = "最終到達（神化形態）: 極限まで高められた絶対的な存在になりました。"
            else:
                desc = f"成長 (Lv.{l}): 日々のタスク消化により絆と生命力が高まりました。"

            history.append({
                'level': l,
                'form': f,
                'desc': desc
            })
        return history

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

    @staticmethod
    def get_base_exp_for_level(lvl):
        if lvl <= 1:
            return 0
        if lvl <= 5:
            return {1: 0, 2: 50, 3: 120, 4: 220, 5: 350}[lvl]
        extra = lvl - 5
        return 350 + extra * 100 + (extra * (extra + 1) // 2) * 25

    @property
    def next_level_exp(self):
        if self.level >= 99:
            return self.get_base_exp_for_level(99)
        return self.get_base_exp_for_level(self.level + 1)

    @property
    def current_level_base_exp(self):
        return self.get_base_exp_for_level(self.level)

    @property
    def exp_progress_percent(self):
        if self.level >= 99:
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
        """EXPに応じてレベル(1〜99)を更新し、レベル上昇があった場合は(True, old_level, new_level)を返す"""
        old_level = self.level
        exp = self.experience

        new_level = 1
        for lvl in range(1, 100):
            if exp >= self.get_base_exp_for_level(lvl):
                new_level = lvl
            else:
                break

        new_level = min(99, max(1, new_level))

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
        # ① 陸地（自然・ガーデニング・リゾート系 - Lv.1〜）
        ('tree', '樹木 🌲'),
        ('palm_tree', 'ヤシの木 🌴'),
        ('broadleaf_tree', '広葉樹 🌳'),
        ('cherry_tree', '桜の木 🌸'),
        ('flower', 'お花 🌸'),
        ('flower_bed', '花壇 🌷'),
        ('sunflower_cluster', 'ヒマワリの群生 🌻'),
        ('garden_light', 'ガーデンライト 💡'),
        ('bonfire', 'かがり火 🔥'),
        ('fountain', '噴水 ⛲'),
        ('small_pond', '小さな池 💧'),
        ('rock', '大きな岩 🪨'),
        ('wooden_bench', '木製ベンチ 🪑'),
        ('hammock', 'ハンモック 🏕️'),
        ('beach_parasol_set', 'ビーチパラソル＆サマーベッド 🏖️'),
        ('wood_deck', 'ウッドデッキ 🪵'),
        ('cafe_table_set', 'カフェテーブルセット ☕'),
        ('watchtower', '見張り台 🗼'),
        ('cottage', 'コテージ風の小屋 🏡'),
        ('house', '小さな家 🏠'),
        ('shop', 'お店 🏪'),
        ('castle', 'お城 🏰'),
        ('animal', '動物 🐶'),
        ('shiba_inu', 'シバイヌ（犬） 🐕'),
        ('calico_cat', '三毛猫（猫） 🐈'),
        ('white_rabbit', '白ウサギ 🐇'),
        ('capybara', 'カピバラ 🦫'),
        ('penguin', 'ペンギン 🐧'),
        ('seagull', '小鳥（カモメ） 🕊️'),
        ('parakeet', '小鳥（インコ） 🦜'),

        # ② 海洋アイテム（Lv.20〜解放）
        ('yacht', 'ヨット ⛵'),
        ('rowboat', '手漕ぎボート 🚣'),
        ('overwater_cottage', '水上コテージ 🏚️'),
        ('swim_ring', '浮き輪 🛟'),
        ('sea_turtle', 'ウミガメ 🐢'),
        ('dolphin_spot', 'イルカのジャンプスポット 🐬'),
        ('lighthouse_islet', '灯台の小島 🏮'),

        # ③ 上空アイテム（Lv.50〜解放）
        ('hot_air_balloon', 'ふわふわ気球 🎈'),
        ('floating_island', '浮島（ラピュタ風ミニアイランド） 🏝️'),
        ('rainbow_arch', '虹のアーチ 🌈'),
        ('meteor_spot', '流星群スポット 🌠'),
        ('airship', '小型飛行艇 🛩️'),
        ('aurora_generator', 'オーロラ発生器 🌌'),
    ]

    ITEM_ICONS = {
        'tree': '🌲',
        'palm_tree': '🌴',
        'broadleaf_tree': '🌳',
        'cherry_tree': '🌸',
        'flower': '🌸',
        'flower_bed': '🌷',
        'sunflower_cluster': '🌻',
        'garden_light': '💡',
        'bonfire': '🔥',
        'fountain': '⛲',
        'small_pond': '💧',
        'rock': '🪨',
        'wooden_bench': '🪑',
        'hammock': '🏕️',
        'beach_parasol_set': '🏖️',
        'wood_deck': '🪵',
        'cafe_table_set': '☕',
        'watchtower': '🗼',
        'cottage': '🏡',
        'house': '🏠',
        'shop': '🏪',
        'castle': '🏰',
        'animal': '🐶',
        'shiba_inu': '🐕',
        'calico_cat': '🐈',
        'white_rabbit': '🐇',
        'capybara': '🦫',
        'penguin': '🐧',
        'seagull': '🕊️',
        'parakeet': '🦜',

        'yacht': '⛵',
        'rowboat': '🚣',
        'overwater_cottage': '🏚️',
        'swim_ring': '🛟',
        'sea_turtle': '🐢',
        'dolphin_spot': '🐬',
        'lighthouse_islet': '🏮',

        'hot_air_balloon': '🎈',
        'floating_island': '🏝️',
        'rainbow_arch': '🌈',
        'meteor_spot': '🌠',
        'airship': '🛩️',
        'aurora_generator': '🌌',
    }

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='island_items', verbose_name="ユーザー")
    item_type = models.CharField("アイテム種類", max_length=50, choices=ITEM_TYPE_CHOICES)
    name = models.CharField("アイテム名", max_length=100)
    position_x = models.FloatField("配置位置X", default=0.0)
    position_y = models.FloatField("配置位置Y", default=0.0)
    position_z = models.FloatField("配置位置Z", default=0.0)
    rotation_y = models.FloatField("Y軸回転", default=0.0)
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

    @property
    def area_category(self):
        ocean_items = {'yacht', 'rowboat', 'overwater_cottage', 'swim_ring', 'sea_turtle', 'dolphin_spot', 'lighthouse_islet'}
        sky_items = {'hot_air_balloon', 'floating_island', 'rainbow_arch', 'meteor_spot', 'airship', 'aurora_generator'}
        if self.item_type in ocean_items:
            return 'ocean'
        elif self.item_type in sky_items:
            return 'sky'
        return 'land'

    @property
    def required_island_level(self):
        cat = self.area_category
        if cat == 'ocean':
            return 20
        elif cat == 'sky':
            return 50
        return 1


class GraduatedCompanion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='graduated_companions', verbose_name="ユーザー")
    companion_type = models.CharField("キャラクター種類", max_length=50, choices=UserCompanion.COMPANION_CHOICES)
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
        forms = UserCompanion.COMPANION_FORMS.get(self.companion_type, {})
        return forms.get(10, forms.get(4, '❓'))


class DepartmentBattle(models.Model):
    STATUS_CHOICES = [
        ('active', '進行中'),
        ('defeated', '討伐完了'),
        ('expired', '期限切れ'),
    ]

    BOSS_ICONS = {
        'dragon': '🐉',
        'robot': '🤖',
        'monster': '👾',
        'golem': '🗿',
    }

    department = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='battles', verbose_name="対象部署")
    boss_type = models.CharField("ボスの種類", max_length=50, default='dragon')
    boss_name = models.CharField("ボス名", max_length=100)
    max_hp = models.IntegerField("最大HP", default=1000)
    current_hp = models.IntegerField("現在HP", default=1000)
    start_date = models.DateTimeField("開始日時", default=timezone.now)
    end_date = models.DateTimeField("終了日時", null=True, blank=True)
    status = models.CharField("ステータス", max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "部署ボス討伐"
        verbose_name_plural = "部署ボス討伐一覧"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.department.name}] {self.boss_name} ({self.get_status_display()})"

    @property
    def icon(self):
        if self.boss_type in self.BOSS_ICONS:
            return self.BOSS_ICONS[self.boss_type]
        for key, icon in self.BOSS_ICONS.items():
            if key in self.boss_name.lower():
                return icon
        return '⚔️'

    @property
    def hp_percent(self):
        if self.max_hp <= 0:
            return 0
        pct = int((max(0, self.current_hp) / self.max_hp) * 100)
        return max(0, min(100, pct))


class DepartmentAchievement(models.Model):
    REQUIREMENT_CHOICES = [
        ('DEFEAT_COUNT', '討伐数'),
        ('ALL_MEMBERS', '全員参加'),
    ]

    code = models.CharField("部署実績コード", max_length=50, unique=True)
    name = models.CharField("実績名 / 称号名", max_length=100)
    description = models.TextField("説明", blank=True, null=True)
    requirement_type = models.CharField("達成条件タイプ", max_length=30, choices=REQUIREMENT_CHOICES, default='DEFEAT_COUNT')
    requirement_value = models.IntegerField("達成必要値", default=1)
    created_at = models.DateTimeField("登録日時", auto_now_add=True)

    class Meta:
        verbose_name = "部署実績・称号"
        verbose_name_plural = "部署実績・称号一覧"
        ordering = ['requirement_type', 'requirement_value', 'created_at']

    def __str__(self):
        return f"{self.name} ({self.code})"


class DepartmentAchievementUnlock(models.Model):
    department = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='unlocked_achievements', verbose_name="部署")
    achievement = models.ForeignKey(DepartmentAchievement, on_delete=models.CASCADE, related_name='unlocked_departments', verbose_name="部署実績")
    unlocked_at = models.DateTimeField("達成日時", auto_now_add=True)

    class Meta:
        verbose_name = "部署獲得実績"
        verbose_name_plural = "部署獲得実績一覧"
        ordering = ['-unlocked_at']
        constraints = [
            models.UniqueConstraint(fields=['department', 'achievement'], name='unique_department_achievement')
        ]

    def __str__(self):
        return f"{self.department.name} - {self.achievement.name}"


class DepartmentProfile(models.Model):
    department = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='department_profile', verbose_name="部署")
    current_title = models.ForeignKey(DepartmentAchievement, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name="現在の部署称号")

    class Meta:
        verbose_name = "部署プロファイル"
        verbose_name_plural = "部署プロファイル一覧"

    def __str__(self):
        title_str = f" ({self.current_title.name})" if self.current_title else ""
        return f"{self.department.name}{title_str}"
