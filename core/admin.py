import csv
import io
import unicodedata
from datetime import timedelta
from django import forms
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter, AdminSite
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.validators import ASCIIUsernameValidator

from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import path
from django.shortcuts import redirect, get_object_or_404, render

from .models import Student, Task, StaffDuty, StaffProfile, Department, SchoolClass, Course, DepartmentGroup
from .forms import UserCSVUploadForm, CSVUploadForm


# ==========================================
# 1. モンキーパッチ（標準機能の上書き）
# ==========================================

# 教職員（User）の表示を「ユーザー名」から「漢字名（姓 名）」に一括変更
def user_full_name_japanese(self):
    full_name = f"{self.last_name} {self.first_name}".strip()
    return full_name if full_name else self.username

User.__str__ = user_full_name_japanese


# 管理画面の左メニューの並び順をカスタム
def custom_get_app_list(self, request, app_label=None):
    app_dict = self._build_app_dict(request, app_label)
    
    model_order = [
        'タスク一覧',
        '学生一覧',
        '学科一覧',
        'コース一覧',
        'クラス一覧',
        '担当業務一覧',
        '教職員プロファイル一覧',
    ]
    
    app_list = sorted(app_dict.values(), key=lambda x: x['name'].lower())
    for app in app_list:
        if app['app_label'] == 'core':
            app['models'].sort(key=lambda x: model_order.index(x['name']) if x['name'] in model_order else 999)
    return app_list

AdminSite.get_app_list = custom_get_app_list


# ==========================================
# 2. 共通関数・カスタムフィルター群
# ==========================================

def normalize_master_name(text):
    """半角カナ→全角、全角英数→半角、小文字→大文字へ完全統一する正規化関数"""
    if not text:
        return ""
    return unicodedata.normalize('NFKC', str(text).strip()).upper()


class LoginStatusFilter(admin.SimpleListFilter):
    title = "ログイン実績"
    parameter_name = "login_status"

    def lookups(self, request, model_admin):
        return (
            ('logged_in', 'ログイン済'),
            ('never', '未ログイン（初回前）'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'logged_in':
            return queryset.filter(last_login__isnull=False)
        if self.value() == 'never':
            return queryset.filter(last_login__isnull=True)
        return queryset


class LeaveStatusFilter(admin.SimpleListFilter):
    title = "休暇設定"
    parameter_name = "leave_status"

    def lookups(self, request, model_admin):
        return (
            ('on_leave', '🌴 休暇中'),
            ('working', '勤務中'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'on_leave':
            return queryset.filter(staff_profile__is_on_leave=True)
        if self.value() == 'working':
            return queryset.filter(staff_profile__is_on_leave=False)
        return queryset


class MultipleNationalityFilter(admin.SimpleListFilter):
    title = "国籍で絞り込む"
    parameter_name = "nationality_in"
    template = "admin/filter_multi_select.html"

    def lookups(self, request, model_admin):
        active_nationalities = (
            Student.objects.exclude(nationality__isnull=True)
            .exclude(nationality="")
            .order_by('nationality')
            .values_list('nationality', flat=True)
            .distinct()
        )
        unique_nationalities = sorted(list(set(n.strip() for n in active_nationalities if n.strip())))
        return [(n, n) for n in unique_nationalities]

    def queryset(self, request, queryset):
        val = self.value()
        if val:
            selected_list = [v.strip() for v in val.split(',') if v.strip()]
            return queryset.filter(nationality__in=selected_list)
        return queryset

    def choices(self, changelist):
        selected_vals = self.value().split(',') if self.value() else []
        all_choice = {
            'selected': not self.value(),
            'query_string': changelist.get_query_string(remove=[self.parameter_name]),
            'display': 'すべて',
            'value': '',
            'query_params': {k: v for k, v in changelist.params.items() if k != self.parameter_name}
        }
        yield all_choice
        for lookup, title in self.lookup_choices:
            yield {
                'selected': lookup in selected_vals,
                'query_string': changelist.get_query_string({self.parameter_name: lookup}),
                'display': title,
                'value': lookup,
                'query_params': {k: v for k, v in changelist.params.items() if k != self.parameter_name}
            }


class ShortClassListFilter(admin.SimpleListFilter):
    """絞り込みフィルターの表記をクラス名のみにするカスタムフィルター"""
    title = 'クラス'
    parameter_name = 'school_class'

    def lookups(self, request, model_admin):
        classes = SchoolClass.objects.all().order_by('name')
        return [(c.id, c.name) for c in classes]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(school_class_id=self.value())
        return queryset


# --- 標準 User の管理画面カスタマイズ ---
class CustomUserCreationForm(UserCreationForm):
    # ユーザー名を半角英数字（ASCII）のみに制限
    username = forms.CharField(
        label='ユーザー名',
        max_length=150,
        help_text='この項目は必須です。半角アルファベット、半角数字、@/./+/-/_ のみで150文字以下にしてください。',
        validators=[ASCIIUsernameValidator()],
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser', 'groups')
        help_texts = {
            'last_name': '姓名の間に半角スペースを空けて入力してください。',
        }

# ▼ 新規追加：既存ユーザー変更用のフォーム ▼
class CustomUserChangeForm(UserChangeForm):
    username = forms.CharField(
        label='ユーザー名',
        max_length=150,
        help_text='この項目は必須です。半角アルファベット、半角数字、@/./+/-/_ のみで150文字以下にしてください。',
        validators=[ASCIIUsernameValidator()],
    )

    class Meta(UserChangeForm.Meta):
        model = User


# 姓(last_name)の表示名を「氏名」に上書き
User._meta.get_field('last_name').verbose_name = '氏名'
User._meta.get_field('last_name').help_text = '姓名の間に半角スペースを空けて入力してください。'

class CustomUserAdmin(BaseUserAdmin):
    change_list_template = "admin/auth/user/change_list.html"
    add_form_template = "admin/change_form.html"

    # ▼ ここに作成した変更用フォームを紐付け ▼
    form = CustomUserChangeForm

    # ▼ 新規追加時（1画面目）の入力レイアウト ▼
    add_form = CustomUserCreationForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('個人情報', {
            'classes': ('wide',),
            'fields': ('last_name', 'email'),
        }),
        ('権限・所属', {
            'classes': ('wide',),
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups'),
        }),
    )

    list_display = (
        'username', 'display_full_name', 'email',
        'display_login_status', 'display_inactivity_alert',
        'display_leave_toggle', 'is_staff', 'display_active_status'
    )
    list_filter = (
        LoginStatusFilter, LeaveStatusFilter,
        'is_staff', 'is_superuser', 'is_active', 'groups'
    )
    actions = ['make_on_leave', 'make_working', 'make_inactive_user']

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('個人情報', {'fields': ('last_name', 'email')}),
        ('権限', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('重要期日', {'fields': ('last_login', 'date_joined')}),
    )

    # ==========================================
    # ▼ 追加：特権昇格の防止と、不要なパーミッションの除外 ▼
    # ==========================================

    def get_fieldsets(self, request, obj=None):
        """スーパーユーザー以外の画面から「スーパーユーザー権限」のチェック枠を隠す（追加・編集画面共通）"""
        # オブジェクトがない（新規追加）場合は add_fieldsets をベースにする
        if not obj:
            fieldsets = self.add_fieldsets
        else:
            fieldsets = super().get_fieldsets(request, obj)
            
        if not request.user.is_superuser:
            new_fieldsets = []
            for name, opts in fieldsets:
                new_opts = opts.copy()
                if 'fields' in new_opts:
                    fields = list(new_opts['fields'])
                    if 'is_superuser' in fields:
                        fields.remove('is_superuser')
                    new_opts['fields'] = tuple(fields)
                new_fieldsets.append((name, new_opts))
            return new_fieldsets
        return fieldsets

    def get_form(self, request, obj=None, **kwargs):
        """フォームの送信データからも「スーパーユーザー権限」をブロック（不正なデータ送信対策）"""
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser and 'is_superuser' in form.base_fields:
            del form.base_fields['is_superuser']
        return form

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """スーパーユーザー以外は「削除権限」や「システム裏側のデータ」を選べないようにフィルタリング"""
        if db_field.name == "user_permissions" and not request.user.is_superuser:
            from django.contrib.auth.models import Permission
            qs = Permission.objects.exclude(
                # ログ・セッション・コンテンツタイプなどのシステムデータを除外
                content_type__app_label__in=['admin', 'contenttypes', 'sessions']
            ).exclude(
                # ダッシュボード側で管理するため不要なデータ ＋ 自身に全権限を付与できる「パーミッション(permission)」を除外
                content_type__model__in=['task', 'taskcomment', 'taskstudentprogress', 'staffprofile', 'staffduty', 'permission']
            ).exclude(
                # 誤操作によるシステム崩壊を防ぐため「削除（Can delete）」の権限をすべて除外
                codename__startswith='delete_'
            )
            kwargs["queryset"] = qs
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    # ==========================================
    # ▲ 追加ここまで ▲
    # ==========================================


    @admin.display(description="状態", ordering="is_active")
    def display_active_status(self, obj):
        if obj.is_active:
            return mark_safe('<span style="background-color: #198754; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em;">有効</span>')
        return mark_safe('<span style="background-color: #dc3545; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em;">停止中</span>')

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="選択されたユーザーを無効化（論理削除）する")
    def make_inactive_user(self, request, queryset):
        if request.POST.get('post'):
            updated = queryset.update(is_active=False)
            self.message_user(request, f"{updated} 名のユーザーを無効化（停止中）にしました。", messages.SUCCESS)
            return None
        context = {
            'queryset': queryset,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        }
        return render(request, 'admin/auth/user/inactive_confirm.html', context)

    @admin.display(description="氏名", ordering="last_name")
    def display_full_name(self, obj):
        return format_html('<span style="white-space: nowrap;">{}</span>', obj.last_name)

    @admin.display(description="ログイン実績")
    def display_login_status(self, obj):
        if obj.last_login:
            login_str = timezone.localtime(obj.last_login).strftime('%Y/%m/%d %H:%M')
            return format_html(
                '<span style="color: #198754; font-weight: bold; white-space: nowrap;">✔ ログイン済</span><br><small style="color: #6c757d; white-space: nowrap;">{}</small>',
                login_str
            )
        return mark_safe('<span style="color: #6c757d; white-space: nowrap;">未ログイン（初回前）</span>')

    @admin.display(description="3日未ログイン警告")
    def display_inactivity_alert(self, obj):
        if hasattr(obj, 'staff_profile') and obj.staff_profile.is_on_leave:
            return mark_safe('<span style="color: #6c757d; font-size: 0.85em; white-space: nowrap;">[休暇中のため免除]</span>')

        threshold = timezone.now() - timedelta(days=3)
        is_inactive = (
            (obj.last_login and obj.last_login <= threshold) or
            (obj.last_login is None and obj.date_joined <= threshold)
        )

        if is_inactive:
            return mark_safe('<span style="background-color: #dc3545; color: white; padding: 2px 7px; border-radius: 4px; font-weight: bold; font-size: 0.85em; white-space: nowrap;">⚠️ 3日以上未ログイン</span>')
        return mark_safe('<span style="color: #198754; font-weight: bold;">正常</span>')

    @admin.display(description="休暇設定")
    def display_leave_toggle(self, obj):
        profile, _ = StaffProfile.objects.get_or_create(user=obj)
        if profile.is_on_leave:
            return format_html(
                '<a class="button" style="background-color: #ffc107; color: #000; font-weight: bold; padding: 3px 8px; border-radius: 4px; text-decoration: none; display: inline-block; text-align: center; line-height: 1.3;" href="toggle-leave/{}/">🌴休暇中<br>（復帰する）</a>',
                obj.pk
            )
        else:
            return format_html(
                '<a class="button" style="background-color: #f8f9fa; border: 1px solid #ced4da; color: #495057; padding: 3px 8px; border-radius: 4px; text-decoration: none; display: inline-block; text-align: center; line-height: 1.3;" href="toggle-leave/{}/">勤務中<br>（休暇にする）</a>',
                obj.pk
            )

    @admin.action(description="選択されたユーザーを休暇にする")
    def make_on_leave(self, request, queryset):
        count = 0
        for user in queryset:
            profile, _ = StaffProfile.objects.get_or_create(user=user)
            if not profile.is_on_leave:
                profile.is_on_leave = True
                profile.save()
                count += 1
        self.message_user(request, f"{count} 名のユーザーを「休暇中」に設定しました。", messages.SUCCESS)

    @admin.action(description="選択されたユーザーを復帰する")
    def make_working(self, request, queryset):
        count = 0
        for user in queryset:
            profile, _ = StaffProfile.objects.get_or_create(user=user)
            if profile.is_on_leave:
                profile.is_on_leave = False
                profile.save()
                count += 1
        self.message_user(request, f"{count} 名のユーザーを「勤務中（復帰）」に設定しました。", messages.SUCCESS)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('toggle-leave/<int:user_id>/', self.admin_site.admin_view(self.toggle_leave), name='user-toggle-leave'),
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='user-import-csv'),
        ]
        return custom_urls + urls

    def toggle_leave(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        profile, _ = StaffProfile.objects.get_or_create(user=user)
        profile.is_on_leave = not profile.is_on_leave
        profile.save()

        status_text = "休暇中" if profile.is_on_leave else "勤務中（通常）"
        self.message_user(request, f"{user.last_name or user.username} さんのステータスを「{status_text}」に変更しました。", messages.SUCCESS)
        return redirect(request.META.get('HTTP_REFERER', '../'))

    def import_csv(self, request):
        if request.method == 'POST':
            form = UserCSVUploadForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['csv_file']
                file_data = csv_file.read()

                try:
                    data_str = file_data.decode('utf-8-sig')
                except UnicodeDecodeError:
                    try:
                        data_str = file_data.decode('cp932')
                    except UnicodeDecodeError:
                        self.message_user(request, 'CSVの文字コードは UTF-8 または Shift-JIS（CP932）でアップロードしてください。', messages.ERROR)
                        return redirect('.')

                import io, csv
                io_string = io.StringIO(data_str)
                reader = csv.reader(io_string)
                next(reader, None)

                success_count = 0
                for row in reader:
                    if not row or len(row) < 3:
                        continue

                    username = row[0].strip()
                    raw_last_name = row[1].strip()
                    raw_first_name = row[2].strip() if len(row) >= 3 else ""
                    combined_name = f"{raw_last_name} {raw_first_name}".strip()
                    email = row[3].strip() if len(row) >= 4 else ""
                    group_name = row[4].strip() if len(row) >= 5 else ""

                    if not username:
                        continue

                    user, created = User.objects.get_or_create(
                        username=username,
                        defaults={
                            'last_name': combined_name,
                            'first_name': '',
                            'email': email,
                            'is_active': True,
                            'is_staff': True,
                            'is_superuser': False,
                        }
                    )

                    if created:
                        user.set_password('aiwa1234')
                        user.save()
                    else:
                        user.last_name = combined_name
                        user.first_name = ''
                        user.email = email
                        user.is_active = True
                        user.is_staff = True
                        user.save()

                    target_group = None
                    if group_name:
                        target_group, _ = Group.objects.get_or_create(name=group_name)
                        user.groups.add(target_group)

                    profile, _ = StaffProfile.objects.get_or_create(user=user)
                    if target_group:
                        profile.department_group = target_group
                        profile.save()

                    success_count += 1

                self.message_user(request, f'{success_count} 名の教職員ユーザーを登録・更新しました。（初期パスワード: aiwa1234）', messages.SUCCESS)
                return redirect('../')
        else:
            form = UserCSVUploadForm()

        context = {
            'title': 'ユーザーCSV一括インポート',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/auth/user/user_import.html', context)


# 既存のUser登録を解除して再登録
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# ==========================================
# 4. 学生・トランザクション・マスタ管理画面
# ==========================================

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'name', 'furigana', 'display_nickname', 'nationality', 'department', 'course', 'display_class', 'display_status')
    list_per_page = 50
    list_filter = ('is_active', MultipleNationalityFilter, 'department', 'course', ShortClassListFilter, 'updated_at')
    search_fields = ('student_id', 'name', 'furigana', 'nickname', 'nationality', 'department__name', 'course__name', 'school_class__name')
    actions = ['make_active', 'make_inactive']

    @admin.display(description="ニックネーム", ordering="nickname")
    def display_nickname(self, obj):
        return obj.nickname if obj.nickname else mark_safe('<span style="color: #adb5bd;">-</span>')
    
    @admin.display(description="クラス", ordering="school_class__name")
    def display_class(self, obj):
        return obj.school_class.name if obj.school_class else "-"

    @admin.display(description="表示状態", ordering="is_active")
    def display_status(self, obj):
        if obj.is_active:
            return mark_safe('<span style="background-color: #198754; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em;">表示</span>')
        return mark_safe('<span style="background-color: #6c757d; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em;">非表示</span>')

    @admin.action(description="選択された学生を「表示」にする")
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} 名の学生を「表示」に変更しました。", messages.SUCCESS)

    @admin.action(description="選択された学生を「非表示」にする")
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} 名の学生を「非表示」に変更しました。", messages.SUCCESS)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='core_student_import_csv'),
        ]
        return custom_urls + urls

    # ▼ 連動プルダウン用のカスタムテンプレート指定とデータ受け渡し ▼
    change_form_template = 'admin/core/student/change_form.html'

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['master_map_json'] = self.get_master_map_json()
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['master_map_json'] = self.get_master_map_json()
        return super().add_view(request, form_url, extra_context=extra_context)

    def get_master_map_json(self):
        import json
        from .models import Course, SchoolClass
        courses = Course.objects.all().values('id', 'name', 'department_id')
        classes = SchoolClass.objects.all().values('id', 'name', 'department_id', 'course_id')

        course_map = {}
        for c in courses:
            dept_id = str(c['department_id'])
            course_map.setdefault(dept_id, []).append({'id': str(c['id']), 'name': c['name']})

        class_map = {}
        for c in classes:
            dept_id = str(c['department_id'])
            class_map.setdefault(dept_id, []).append({
                'id': str(c['id']), 
                'name': c['name'], 
                'course_id': str(c['course_id']) if c['course_id'] else ''
            })

        data = {'courses': course_map, 'classes': class_map}
        return json.dumps(data, ensure_ascii=False)
    
    def import_csv(self, request):
        if request.method == 'POST':
            form = CSVUploadForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['csv_file']
                file_data = csv_file.read()

                try:
                    data_str = file_data.decode('utf-8-sig')
                except UnicodeDecodeError:
                    try:
                        data_str = file_data.decode('cp932')
                    except UnicodeDecodeError:
                        self.message_user(request, 'CSVの文字コードは UTF-8 または Shift-JIS形式でアップロードしてください。', level=messages.ERROR)
                        return redirect('..')

                io_string = io.StringIO(data_str)
                reader = csv.reader(io_string)
                next(reader, None)

                success_count = new_dept = new_course = new_class = 0

                for row in reader:
                    if not row or len(row) < 3:
                        continue

                    student_id = row[0].strip()
                    name = row[1].strip()

                    furigana = nickname = nationality = dept_str = course_str = class_str = ""

                    if len(row) >= 8:
                        furigana, nickname, nationality, dept_str, course_str, class_str = [r.strip() for r in row[2:8]]
                    elif len(row) == 7:
                        furigana, nickname, nationality, dept_str, class_str = [r.strip() for r in row[2:7]]
                    elif len(row) == 6:
                        furigana, nickname, dept_str, class_str = [r.strip() for r in row[2:6]]
                    elif len(row) == 5:
                        furigana, dept_str, class_str = [r.strip() for r in row[2:5]]
                    elif len(row) == 4:
                        dept_str, class_str = [r.strip() for r in row[2:4]]
                    else:
                        dept_str = row[2].strip()

                    dept_name = normalize_master_name(dept_str)
                    course_name = normalize_master_name(course_str)
                    class_name = normalize_master_name(class_str)

                    dept_obj = course_obj = class_obj = None

                    if dept_name:
                        dept_obj, created = Department.objects.get_or_create(name=dept_name)
                        if created: new_dept += 1
                        
                        if course_name:
                            course_obj, created = Course.objects.get_or_create(department=dept_obj, name=course_name)
                            if created: new_course += 1
                            
                        if class_name:
                            class_obj, created = SchoolClass.objects.get_or_create(
                                department=dept_obj,
                                course=course_obj,
                                name=class_name
                            )
                            if created: new_class += 1

                    Student.objects.update_or_create(
                        student_id=student_id,
                        defaults={
                            'name': name,
                            'furigana': furigana,
                            'nickname': nickname if nickname else None,
                            'nationality': nationality if nationality else None,
                            'department': dept_obj,
                            'course': course_obj,
                            'school_class': class_obj,
                            'is_active': True,
                        }
                    )
                    success_count += 1

                msg = f'{success_count} 名を取り込みました。'
                if new_dept or new_course or new_class:
                    msg += f'（新規マスタ生成：学科 {new_dept}件 / コース {new_course}件 / クラス {new_class}件）'
                self.message_user(request, msg, level=messages.SUCCESS)
                return redirect('..')
        else:
            form = CSVUploadForm()

        context = {
            'title': '📥 学生CSV 一括インポート',
            'form': form,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
            'has_permission': True,
        }
        return render(request, 'admin/core/student/student_import.html', context)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'target_type', 'target_group', 'priority', 'status', 'due_date')
    list_filter = ('status', 'priority', 'target_group', 'privacy')
    search_fields = ('title', 'description')
    date_hierarchy = 'due_date'


# --- 所属部署（親）と担当業務（子）のネスト管理 ---
class StaffDutyInline(admin.TabularInline):
    model = StaffDuty
    extra = 1

@admin.register(DepartmentGroup)
class DepartmentGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_duties_count')
    search_fields = ('name',)
    fields = ('name',)
    inlines = [StaffDutyInline]

    @admin.display(description="登録業務数")
    def display_duties_count(self, obj):
        return f"{obj.duties.count()} 業務"

# --- 教職員プロファイル用のカスタムフォーム ---
class StaffProfileForm(forms.ModelForm):
    # 複数選択可能な「所属部署」ウィジェットを作成（不要な✏️や＋ボタンも消えます）
    departments = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=FilteredSelectMultiple("所属（部・課）", is_stacked=False),
        required=False,
        label="所属（部・課）"
    )

    class Meta:
        model = StaffProfile
        # 既存の1つしか選べない枠を画面から隠す
        exclude = ('department_group',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 開いた時に、現在の所属部署を初期セットする
        if self.instance and self.instance.pk and self.instance.user:
            self.fields['departments'].initial = self.instance.user.groups.all()

    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            profile.save()
            
        if profile.user:
            # 画面で選ばれた複数の部署をシステムに同期保存
            selected_depts = self.cleaned_data.get('departments')
            profile.user.groups.set(selected_depts)
            
            # 既存のシステム（1部署想定）がエラーにならないよう、裏側で1つ目の部署を自動セット
            profile.department_group = selected_depts.first() if selected_depts else None
            profile.save()
            
        self.save_m2m()
        return profile

@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    form = StaffProfileForm
    list_display = ('display_user', 'display_departments', 'display_duties')
    
    # ▼ 追加・変更：絞り込みフィルターに department_group (所属部署) を追加
    list_filter = ('department_group', 'is_on_leave')
    
    # ▼ 追加：教職員アカウント(username/氏名)と、担当業務名(duties__name)での検索ボックスを実装
    search_fields = ('user__username', 'user__last_name', 'user__first_name', 'duties__name')
    
    filter_horizontal = ('duties',)

    fields = ('user', 'departments', 'duties')
    readonly_fields = ('user',)

    @admin.display(description="教職員アカウント", ordering="user__username")
    def display_user(self, obj):
        full_name = f"{obj.user.last_name} {obj.user.first_name}".strip()
        name = full_name if full_name else obj.user.username
        return f"{name}（{obj.user.username}）"

    @admin.display(description="所属部署")
    def display_departments(self, obj):
        depts = [g.name for g in obj.user.groups.all()]
        return "、".join(depts) if depts else "無所属"

    @admin.display(description="担当業務")
    def display_duties(self, obj):
        duties = [d.name for d in obj.duties.all()]
        return "、".join(duties) if duties else "未設定"

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "duties":
            object_id = request.resolver_match.kwargs.get('object_id')
            if object_id:
                profile = StaffProfile.objects.filter(pk=object_id).first()
                if profile and profile.user:
                    user_groups = profile.user.groups.all()
                    kwargs["queryset"] = StaffDuty.objects.filter(department_group__in=user_groups)
                else:
                    kwargs["queryset"] = StaffDuty.objects.none()
            else:
                kwargs["queryset"] = StaffDuty.objects.none()
                
        return super().formfield_for_manytomany(db_field, request, **kwargs)


# --- 学科・コース・クラスの階層構造（インライン表示） ---
class CourseInline(admin.TabularInline):
    model = Course
    extra = 1

class SchoolClassInline(admin.TabularInline):
    model = SchoolClass
    extra = 1

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'display_courses_count', 'display_classes_count')
    inlines = [CourseInline, SchoolClassInline]

    @admin.display(description="登録コース数")
    def display_courses_count(self, obj):
        return f"{obj.courses.count()} コース"

    @admin.display(description="登録クラス数")
    def display_classes_count(self, obj):
        return f"{obj.classes.count()} クラス"


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'department')
    list_filter = ('department',)
    search_fields = ('name', 'department__name')


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'course')
    list_filter = ('department', 'course')
    search_fields = ('name', 'department__name', 'course__name')