import os
import random
import django

# Django環境の初期化
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aiwa.settings')
django.setup()

from core.models import Student, Department, Course, SchoolClass

def run():
    print("--- ダミー学生（100名）の一括生成を開始します ---")

    # 1. 学科・コース・クラスマスタのセットアップ（存在しない場合は自動生成）
    dept_data = [
        {"name": "アニメーション学科", "courses": ["作画・アニメーターコース", "3DCG・CGアニメコース"], "classes": ["Aクラス", "Bクラス"]},
        {"name": "コミック・イラスト学科", "courses": ["キャラクターイラストコース", "マンガコース"], "classes": ["1組", "2組"]},
        {"name": "ゲームクリエイター学科", "courses": ["ゲームプログラミングコース", "ゲームプランナーコース"], "classes": ["午前クラス", "午後クラス"]},
    ]

    class_pool = []
    for d in dept_data:
        dept, _ = Department.objects.get_or_create(name=d["name"])
        for c_name in d["courses"]:
            # Courseモデルが存在する場合
            course, _ = Course.objects.get_or_create(name=c_name, department=dept)
            for cl_name in d["classes"]:
                s_class, _ = SchoolClass.objects.get_or_create(
                    name=f"{d['name']} {cl_name}",
                    defaults={"department": dept}
                )
                class_pool.append({
                    "department": dept,
                    "course": course,
                    "school_class": s_class,
                })

    # 2. 姓名データ（日本人名 + 国際校向けの留学生名）
    names_jp = [
        ("佐藤", "健太", "サトウ", "ケンタ"), ("鈴木", "美咲", "スズキ", "ミサキ"),
        ("高橋", "翼", "タカハシ", "ツバサ"), ("田中", "結衣", "タナカ", "ユイ"),
        ("伊藤", "拓海", "イトウ", "タクミ"), ("渡辺", "葵", "ワタナベ", "アオイ"),
        ("山本", "駿", "ヤマモト", "シュン"), ("中村", "陽菜", "ナカムラ", "ハルナ"),
        ("小林", "大樹", "コバヤシ", "ダイキ"), ("加藤", "莉央", "カトウ", "リオ"),
        ("吉田", "琉生", "ヨシダ", "ルイ"), ("山田", "杏奈", "ヤマダ", "アンナ"),
        ("佐々木", "陸", "ササキ", "リク"), ("山口", "凛", "ヤマグチ", "リン"),
        ("斉藤", "蓮", "サイトウ", "レン"), ("松本", "桜", "マツモト", "サクラ"),
        ("井上", "翔太", "イノウエ", "ショウタ"), ("木村", "萌", "キムラ", "モエ"),
        ("林", "斗真", "ハヤシ", "トウマ"), ("清水", "詩織", "シミズ", "シオリ"),
        ("山崎", "颯太", "ヤマザキ", "ソウタ"), ("池田", "菜々美", "イケダ", "ナナミ"),
        ("橋本", "陸斗", "ハシモト", "リクト"), ("阿部", "美優", "アベ", "ミユ"),
        ("森", "蒼空", "モリ", "ソラ"), ("石川", "大和", "イシカワ", "ヤマト"),
    ]

    names_global = [
        ("Nguyen", "Van An", "グエン", "ヴァン アン", "ベトナム"),
        ("Tran", "Thi Mai", "チャン", "ティ マイ", "ベトナム"),
        ("Kim", "Minjun", "キム", "ミンジュン", "韓国"),
        ("Lee", "Seoyeon", "イ", "ソヨン", "韓国"),
        ("Wang", "Wei", "ワン", "ウェイ", "中国"),
        ("Zhang", "Li", "ジャン", "リー", "中国"),
        ("Smith", "James", "スミス", "ジェームズ", "アメリカ"),
        ("Garcia", "Maria", "ガルシア", "マリア", "フィリピン"),
    ]

    created_count = 0

    for i in range(1, 101):
        student_id = f"2026{i:04d}"  # 20260001〜20260100
        
        # 80%は日本人、20%は留学生
        if random.random() < 0.8:
            last, first, last_f, first_f = random.choice(names_jp)
            full_name = f"{last} {first}"
            furigana = f"{last_f} {first_f}"
            nationality = "日本"
            nickname = first
        else:
            last, first, last_f, first_f, country = random.choice(names_global)
            full_name = f"{last} {first}"
            furigana = f"{last_f} {first_f}"
            nationality = country
            nickname = first

        # 所属学科・コース・クラスをランダム割当
        assignment = random.choice(class_pool)

        # 登録・更新
        student, created = Student.objects.update_or_create(
            student_id=student_id,
            defaults={
                "name": full_name,
                "furigana": furigana,
                "nickname": nickname,
                "department": assignment["department"],
                "course": assignment["course"],
                "school_class": assignment["school_class"],
                "nationality": nationality,
                "is_active": True,
            }
        )
        created_count += 1

    print(f"✅ 完了: 合計 {created_count} 名の学生データを登録・同期しました！")

if __name__ == '__main__':
    run()