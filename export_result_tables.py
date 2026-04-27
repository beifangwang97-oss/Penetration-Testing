import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


BASE_DIR = Path(__file__).resolve().parent
REPORT_PATH = BASE_DIR / "results" / "evaluations" / "eval_20260426_202749_6906" / "final_report.json"
OUTPUT_DIR = BASE_DIR / "results" / "picture"


def pct(value: float) -> str:
    return f"{value * 100:.2f}"


def build_tables(results: dict) -> list[tuple[str, str, list[str], list[list[str]]]]:
    model_order = [
        "Gemini 3.1 Flash Lite | google/gemini-3.1-flash-lite-preview",
        "Qwen 3.5 Flash | qwen/qwen3.5-flash-02-23",
        "DeepSeek V3.2 | deepseek/deepseek-v3.2",
        "GPT-4o Mini | openai/gpt-4o-mini",
        "Doubao Seed 1.6 Flash | bytedance-seed/seed-1.6-flash",
    ]
    model_short = {
        "Gemini 3.1 Flash Lite | google/gemini-3.1-flash-lite-preview": "Gemini 3.1 Flash Lite",
        "Qwen 3.5 Flash | qwen/qwen3.5-flash-02-23": "Qwen 3.5 Flash",
        "DeepSeek V3.2 | deepseek/deepseek-v3.2": "DeepSeek V3.2",
        "GPT-4o Mini | openai/gpt-4o-mini": "GPT-4o Mini",
        "Doubao Seed 1.6 Flash | bytedance-seed/seed-1.6-flash": "Doubao Seed 1.6 Flash",
    }

    table_41 = (
        "table_4_1_dataset_composition",
        "表4-1 正式实验数据集组成",
        ["题型", "文件名", "题目数量"],
        [
            ["JU", "review_gemini-3.1-flash-lite-preview_JU_832.jsonl", "832"],
            ["MC", "review_gemini-3.1-flash-lite-preview_MC_422.jsonl", "422"],
            ["MSR", "review_gemini-3.1-flash-lite-preview_MSR_392.jsonl", "392"],
            ["SAR", "review_gemini-3.1-flash-lite-preview_SAR_401.jsonl", "401"],
            ["SC", "review_gemini-3.1-flash-lite-preview_SC_4173.jsonl", "4173"],
            ["SQ", "review_gemini-3.1-flash-lite-preview_SQ_412.jsonl", "412"],
            ["SSC", "review_gemini-3.1-flash-lite-preview_SSC_405.jsonl", "405"],
            ["合计", "-", "7037"],
        ],
    )

    table_42_rows = []
    for label in model_order:
        item = results[label]
        table_42_rows.append(
            [
                model_short[label],
                str(item["total_questions"]),
                str(item["correct"]),
                pct(item["accuracy"]),
                pct(item["average_score"]),
            ]
        )
    table_42 = (
        "table_4_2_overall_performance",
        "表4-2 不同模型总体性能对比",
        ["模型名称", "总题数", "正确题数", "准确率/%", "平均得分/%"],
        table_42_rows,
    )

    qtypes = [
        ("judgment", "JU"),
        ("multiple_choice", "MC"),
        ("scenario_multi_step_reasoning", "MSR"),
        ("short_answer_reasoning", "SAR"),
        ("single_choice", "SC"),
        ("sequencing", "SQ"),
        ("scenario_single_choice", "SSC"),
    ]
    table_43_rows = []
    table_44_rows = []
    table_45_rows = []
    for label in model_order:
        item = results[label]
        qstats = item["question_types"]
        row_acc = [model_short[label]]
        row_score = [model_short[label]]
        acc_values = []
        score_values = []
        for key, short in qtypes:
            acc = qstats[key]["accuracy"]
            score = qstats[key]["average_score"]
            row_acc.append(pct(acc))
            row_score.append(pct(score))
            acc_values.append(acc)
            score_values.append(score)
        table_43_rows.append(row_acc)
        table_44_rows.append(row_score)
        table_45_rows.append(
            [
                model_short[label],
                f"{sum(acc_values) / len(acc_values) * 100:.2f}",
                f"{sum(score_values) / len(score_values) * 100:.2f}",
            ]
        )

    table_43 = (
        "table_4_3_accuracy_by_type",
        "表4-3 不同模型在各题型上的准确率对比",
        ["模型名称", "JU/%", "MC/%", "MSR/%", "SAR/%", "SC/%", "SQ/%", "SSC/%"],
        table_43_rows,
    )
    table_44 = (
        "table_4_4_score_by_type",
        "表4-4 不同模型在各题型上的平均得分对比",
        ["模型名称", "JU/%", "MC/%", "MSR/%", "SAR/%", "SC/%", "SQ/%", "SSC/%"],
        table_44_rows,
    )
    table_45 = (
        "table_4_5_macro_average",
        "表4-5 不同模型题型等权宏平均结果",
        ["模型名称", "宏平均准确率/%", "宏平均得分/%"],
        table_45_rows,
    )
    return [table_41, table_42, table_43, table_44, table_45]


def render_table(title: str, columns: list[str], rows: list[list[str]], image_path: Path, pdf: PdfPages) -> None:
    ncols = len(columns)
    nrows = len(rows)
    width = max(12, ncols * 2.2)
    height = max(3.4, 1.0 + 0.42 * (nrows + 1))
    fig, ax = plt.subplots(figsize=(width, height), dpi=220)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_title(title, fontsize=16, fontweight="bold", pad=14)

    col_widths = [0.18] * ncols
    if ncols == 3:
        col_widths = [0.12, 0.62, 0.14]
    elif ncols == 5:
        col_widths = [0.32, 0.12, 0.12, 0.12, 0.14]
    elif ncols == 8:
        col_widths = [0.24] + [0.10] * 7

    table = ax.table(
        cellText=rows,
        colLabels=columns,
        cellLoc="center",
        colLoc="center",
        colWidths=col_widths,
        bbox=[0.02, 0.02, 0.96, 0.88],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10.5)
    table.scale(1, 1.35)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#cfd8e3")
        cell.set_linewidth(0.8)
        if row == 0:
            cell.set_facecolor("#eaf0f8")
            cell.set_text_props(weight="bold")
        else:
            cell.set_facecolor("#ffffff" if row % 2 else "#f8fafc")
        if col == 0 and row > 0:
            cell.set_text_props(weight="bold")

    fig.savefig(image_path, bbox_inches="tight", facecolor="white")
    pdf.savefig(fig, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    tables = build_tables(report["results"])

    pdf_path = OUTPUT_DIR / "chapter4_tables.pdf"
    with PdfPages(pdf_path) as pdf:
        for stem, title, columns, rows in tables:
            render_table(title, columns, rows, OUTPUT_DIR / f"{stem}.jpg", pdf)

    print(f"exported_tables={len(tables)}")
    print(f"output_dir={OUTPUT_DIR}")
    print(f"pdf={pdf_path}")


if __name__ == "__main__":
    main()
