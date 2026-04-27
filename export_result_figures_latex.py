import json
import shutil
import subprocess
from pathlib import Path

import fitz
from PIL import Image


BASE_DIR = Path(__file__).resolve().parent
REPORT_PATH = BASE_DIR / "results" / "evaluations" / "eval_20260426_202749_6906" / "final_report.json"
OUTPUT_DIR = BASE_DIR / "results" / "picture"
BUILD_DIR = OUTPUT_DIR / "_latex_build"


MODEL_ORDER = [
    "Gemini 3.1 Flash Lite | google/gemini-3.1-flash-lite-preview",
    "Qwen 3.5 Flash | qwen/qwen3.5-flash-02-23",
    "DeepSeek V3.2 | deepseek/deepseek-v3.2",
    "GPT-4o Mini | openai/gpt-4o-mini",
    "Doubao Seed 1.6 Flash | bytedance-seed/seed-1.6-flash",
]

MODEL_SHORT = {
    "Gemini 3.1 Flash Lite | google/gemini-3.1-flash-lite-preview": "Gemini 3.1 Flash Lite",
    "Qwen 3.5 Flash | qwen/qwen3.5-flash-02-23": "Qwen 3.5 Flash",
    "DeepSeek V3.2 | deepseek/deepseek-v3.2": "DeepSeek V3.2",
    "GPT-4o Mini | openai/gpt-4o-mini": "GPT-4o Mini",
    "Doubao Seed 1.6 Flash | bytedance-seed/seed-1.6-flash": "Doubao Seed 1.6 Flash",
}

MODEL_COLOR = {
    "Gemini 3.1 Flash Lite | google/gemini-3.1-flash-lite-preview": "1F4FB4",
    "Qwen 3.5 Flash | qwen/qwen3.5-flash-02-23": "0E7490",
    "DeepSeek V3.2 | deepseek/deepseek-v3.2": "6D28D9",
    "GPT-4o Mini | openai/gpt-4o-mini": "D97706",
    "Doubao Seed 1.6 Flash | bytedance-seed/seed-1.6-flash": "BE3F3F",
}

QTYPE_ORDER = [
    ("judgment", "JU"),
    ("multiple_choice", "MC"),
    ("scenario_multi_step_reasoning", "MSR"),
    ("short_answer_reasoning", "SAR"),
    ("single_choice", "SC"),
    ("sequencing", "SQ"),
    ("scenario_single_choice", "SSC"),
]

CAP_ORDER = [
    ("fact_verification", "Fact"),
    ("tactic_classification", "Tactic"),
    ("technique_purpose", "Purpose"),
    ("tool_mapping", "Tool"),
    ("defense_detection", "Defense"),
    ("attack_scenario", "AtkScene"),
    ("scenario_technique_identification", "ScenTech"),
    ("technique_association_analysis", "Assoc"),
    ("cross_tactic_correlation_analysis", "Cross"),
    ("multi_step_reasoning", "MSR"),
    ("short_answer_technique_judgment", "SAR"),
]


def load_results() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))["results"]


def pct(value: float) -> str:
    return f"{value * 100:.2f}"


def tex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "_": r"\_",
        "#": r"\#",
        "{": r"\{",
        "}": r"\}",
    }
    escaped = []
    for char in text:
        escaped.append(replacements.get(char, char))
    return "".join(escaped)


def hex_to_tex_rgb(hex_code: str) -> str:
    red = int(hex_code[0:2], 16)
    green = int(hex_code[2:4], 16)
    blue = int(hex_code[4:6], 16)
    return f"{{rgb,255:red,{red};green,{green};blue,{blue}}}"


def tex_preamble() -> str:
    return r"""
\documentclass[tikz,border=6pt]{standalone}
\usepackage{ctex}
\usepackage{booktabs}
\usepackage{array}
\usepackage{pgfplots}
\usepgfplotslibrary{polar}
\usepackage{xcolor}
\usepackage{tabularx}
\usepackage{makecell}
\usepackage{colortbl}
\pgfplotsset{compat=1.18}
\definecolor{linecolor}{HTML}{D7DFEB}
\definecolor{headbg}{HTML}{EAF0F8}
\definecolor{altbg}{HTML}{F8FAFC}
\begin{document}
"""


def reset_build_dir() -> None:
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def pdf_to_jpg(pdf_path: Path, jpg_path: Path, dpi: int = 260) -> None:
    scale = dpi / 72.0
    with fitz.open(pdf_path) as doc:
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        png_path = jpg_path.with_suffix(".png")
        pix.save(png_path)
    with Image.open(png_path) as img:
        img.convert("RGB").save(jpg_path, quality=95)
    png_path.unlink(missing_ok=True)


def write_and_compile(stem: str, body: str) -> None:
    tex_path = BUILD_DIR / f"{stem}.tex"
    tex_path.write_text(tex_preamble() + body + "\n\\end{document}\n", encoding="utf-8")
    subprocess.run(
        ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
        cwd=BUILD_DIR,
        check=True,
    )

    pdf_src = BUILD_DIR / f"{stem}.pdf"
    pdf_dst = OUTPUT_DIR / f"{stem}.pdf"
    shutil.copy2(pdf_src, pdf_dst)
    pdf_to_jpg(pdf_dst, OUTPUT_DIR / f"{stem}.jpg")


def make_table_tex(columns: list[str], rows: list[list[str]], widths: list[str]) -> str:
    colspec = "".join(widths)
    header = " & ".join(tex_escape(col) for col in columns) + r" \\"
    lines = [
        r"\begin{tabular}{" + colspec + "}",
        r"\toprule",
        r"\rowcolor{headbg}",
        header,
        r"\midrule",
    ]
    for idx, row in enumerate(rows, start=1):
        if idx % 2 == 0:
            lines.append(r"\rowcolor{altbg}")
        lines.append(" & ".join(tex_escape(cell) for cell in row) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    return "\n".join(lines)


def export_tables(results: dict) -> None:
    table_rows = [
        ["JU", "review_gemini-3.1-flash-lite-preview_JU_832.jsonl", "832"],
        ["MC", "review_gemini-3.1-flash-lite-preview_MC_422.jsonl", "422"],
        ["MSR", "review_gemini-3.1-flash-lite-preview_MSR_392.jsonl", "392"],
        ["SAR", "review_gemini-3.1-flash-lite-preview_SAR_401.jsonl", "401"],
        ["SC", "review_gemini-3.1-flash-lite-preview_SC_4173.jsonl", "4173"],
        ["SQ", "review_gemini-3.1-flash-lite-preview_SQ_412.jsonl", "412"],
        ["SSC", "review_gemini-3.1-flash-lite-preview_SSC_405.jsonl", "405"],
        ["总计", "-", "7037"],
    ]
    write_and_compile(
        "table_4_1_dataset_composition",
        r"\centering" + "\n" + make_table_tex(["题型", "文件名", "题目数"], table_rows, ["c", "p{10.8cm}", "c"]),
    )

    overall_rows = []
    acc_rows = []
    score_rows = []
    macro_rows = []
    for label in MODEL_ORDER:
        item = results[label]
        overall_rows.append(
            [
                MODEL_SHORT[label],
                str(item["total_questions"]),
                str(item["correct"]),
                pct(item["accuracy"]),
                pct(item["average_score"]),
            ]
        )

        qstats = item["question_types"]
        acc_values = []
        score_values = []
        acc_row = [MODEL_SHORT[label]]
        score_row = [MODEL_SHORT[label]]
        for key, _ in QTYPE_ORDER:
            acc_values.append(qstats[key]["accuracy"])
            score_values.append(qstats[key]["average_score"])
            acc_row.append(pct(qstats[key]["accuracy"]))
            score_row.append(pct(qstats[key]["average_score"]))
        acc_rows.append(acc_row)
        score_rows.append(score_row)
        macro_rows.append(
            [
                MODEL_SHORT[label],
                f"{sum(acc_values) / len(acc_values) * 100:.2f}",
                f"{sum(score_values) / len(score_values) * 100:.2f}",
            ]
        )

    write_and_compile(
        "table_4_2_overall_performance",
        r"\centering" + "\n" + make_table_tex(["模型", "总题数", "答对数", "准确率/%", "平均得分/%"], overall_rows, ["p{4.2cm}", "c", "c", "c", "c"]),
    )
    write_and_compile(
        "table_4_3_accuracy_by_type",
        r"\centering" + "\n" + make_table_tex(["模型", "JU/%", "MC/%", "MSR/%", "SAR/%", "SC/%", "SQ/%", "SSC/%"], acc_rows, ["p{4.2cm}", "c", "c", "c", "c", "c", "c", "c"]),
    )
    write_and_compile(
        "table_4_4_score_by_type",
        r"\centering" + "\n" + make_table_tex(["模型", "JU/%", "MC/%", "MSR/%", "SAR/%", "SC/%", "SQ/%", "SSC/%"], score_rows, ["p{4.2cm}", "c", "c", "c", "c", "c", "c", "c"]),
    )
    write_and_compile(
        "table_4_5_macro_average",
        r"\centering" + "\n" + make_table_tex(["模型", "宏平均准确率/%", "宏平均得分/%"], macro_rows, ["p{4.2cm}", "c", "c"]),
    )


def bar_chart_tex(labels: list[str], coords: str, color: str, ylabel: str, ymax: int, width: str = "17cm", height: str = "8.1cm") -> str:
    tex_color = hex_to_tex_rgb(color)
    xticks = ",".join(str(i) for i in range(len(labels)))
    xticklabels = ",".join(tex_escape(label) for label in labels)
    ylabel = tex_escape(ylabel)
    return rf"""
\begin{{tikzpicture}}
\begin{{axis}}[
width={width},
height={height},
ybar,
bar width=16pt,
ymin=0,
ymax={ymax},
xtick={{{xticks}}},
xticklabels={{{xticklabels}}},
xticklabel style={{rotate=18, anchor=east, font=\small}},
ylabel={{{ylabel}}},
grid=both,
major grid style={{draw=linecolor}},
minor grid style={{draw=linecolor!55}},
nodes near coords,
nodes near coords align={{vertical}},
every node near coord/.append style={{font=\small}},
axis line style={{draw=linecolor}},
tick style={{draw=linecolor}},
]
\addplot[fill={tex_color}, draw={tex_color}] coordinates {{
{coords}
}};
\end{{axis}}
\end{{tikzpicture}}
"""


def export_bar_charts(results: dict) -> None:
    model_labels = [MODEL_SHORT[m] for m in MODEL_ORDER]
    acc_coords = "\n".join(f"({idx},{results[m]['accuracy'] * 100:.2f})" for idx, m in enumerate(MODEL_ORDER))
    score_coords = "\n".join(f"({idx},{results[m]['average_score'] * 100:.2f})" for idx, m in enumerate(MODEL_ORDER))
    type_counts = [("JU", 832), ("MC", 422), ("MSR", 392), ("SAR", 401), ("SC", 4173), ("SQ", 412), ("SSC", 405)]
    count_coords = "\n".join(f"({idx},{v})" for idx, (_, v) in enumerate(type_counts))

    write_and_compile(
        "figure_4_1_dataset_distribution",
        bar_chart_tex([k for k, _ in type_counts], count_coords, "1F4FB4", "题目数量", 4600),
    )
    write_and_compile(
        "figure_4_2_overall_accuracy",
        bar_chart_tex(model_labels, acc_coords, "0E7490", "准确率 / %", 100),
    )
    write_and_compile(
        "figure_4_3_overall_average_score",
        bar_chart_tex(model_labels, score_coords, "6D28D9", "平均得分 / %", 100),
    )


def export_question_type_heatmap(results: dict) -> None:
    x_labels = [MODEL_SHORT[m] for m in MODEL_ORDER]
    y_labels = [abbr for _, abbr in QTYPE_ORDER]
    rows = []
    for yi, (key, _) in enumerate(QTYPE_ORDER):
        for xi, model in enumerate(MODEL_ORDER):
            rows.append(f"{xi} {yi} {results[model]['question_types'][key]['accuracy'] * 100:.2f}")

    tex = rf"""
\begin{{tikzpicture}}
\begin{{axis}}[
width=17cm,
height=8.5cm,
colormap={{custom}}{{color(0cm)=(white); color(1cm)=(blue!15); color(2cm)=(blue!70)}},
colorbar,
point meta min=0,
point meta max=100,
xmin=-0.5, xmax={len(x_labels)-0.5},
ymin=-0.5, ymax={len(y_labels)-0.5},
xtick={{0,...,{len(x_labels)-1}}},
ytick={{0,...,{len(y_labels)-1}}},
xticklabels={{{",".join(x_labels)}}},
yticklabels={{{",".join(y_labels)}}},
xticklabel style={{rotate=18, anchor=east, font=\small}},
yticklabel style={{font=\small}},
]
\addplot[
matrix plot*,
mesh/cols={len(x_labels)},
point meta=explicit,
nodes near coords,
every node near coord/.append style={{font=\scriptsize, text=black}},
] table[meta index=2] {{
{chr(10).join(rows)}
}};
\end{{axis}}
\end{{tikzpicture}}
"""
    write_and_compile("figure_4_4_question_type_accuracy_heatmap", tex)


def export_capability_radar(results: dict) -> None:
    angles = [i * 360 / len(CAP_ORDER) for i in range(len(CAP_ORDER))]
    xticks = ",".join(f"{a:.3f}" for a in angles)
    xticklabels = ",".join(label for _, label in CAP_ORDER)

    plots = []
    for model in MODEL_ORDER:
        coords = []
        for angle, (key, _) in zip(angles, CAP_ORDER):
            value = results[model]["type_analysis"].get(key, {}).get("average_score", 0) * 100
            coords.append(f"({angle:.3f},{value:.2f})")
        coords.append(coords[0])
        tex_color = hex_to_tex_rgb(MODEL_COLOR[model])
        plots.append(
            rf"\addplot+[mark=*, mark size=1.8pt, line width=1.0pt, color={tex_color}, fill={tex_color}, fill opacity=0.05] coordinates {{{' '.join(coords)}}};"
            + "\n"
            + rf"\addlegendentry{{{MODEL_SHORT[model]}}}"
        )

    tex = rf"""
\begin{{tikzpicture}}
\begin{{polaraxis}}[
width=17cm,
height=11cm,
grid=both,
ymin=0,
ymax=100,
xtick={{{xticks}}},
xticklabels={{{xticklabels}}},
xticklabel style={{font=\small}},
ytick={{20,40,60,80,100}},
yticklabel style={{font=\scriptsize}},
legend style={{at={{(0.5,-0.14)}}, anchor=north, legend columns=2, draw=none, font=\small}},
]
{chr(10).join(plots)}
\end{{polaraxis}}
\end{{tikzpicture}}
"""
    write_and_compile("figure_4_5_capability_radar", tex)


def export_capability_heatmap(results: dict) -> None:
    x_labels = [MODEL_SHORT[m] for m in MODEL_ORDER]
    y_labels = [abbr for _, abbr in CAP_ORDER]
    rows = []
    for yi, (key, _) in enumerate(CAP_ORDER):
        for xi, model in enumerate(MODEL_ORDER):
            value = results[model]["type_analysis"].get(key, {}).get("average_score", 0) * 100
            rows.append(f"{xi} {yi} {value:.2f}")

    tex = rf"""
\begin{{tikzpicture}}
\begin{{axis}}[
width=18cm,
height=9cm,
colormap={{custom}}{{color(0cm)=(white); color(1cm)=(teal!20); color(2cm)=(teal!80)}},
colorbar,
point meta min=0,
point meta max=100,
xmin=-0.5, xmax={len(x_labels)-0.5},
ymin=-0.5, ymax={len(y_labels)-0.5},
xtick={{0,...,{len(x_labels)-1}}},
ytick={{0,...,{len(y_labels)-1}}},
xticklabels={{{",".join(x_labels)}}},
yticklabels={{{",".join(y_labels)}}},
xticklabel style={{rotate=18, anchor=east, font=\small}},
yticklabel style={{font=\small}},
]
\addplot[
matrix plot*,
mesh/cols={len(x_labels)},
point meta=explicit,
nodes near coords,
every node near coord/.append style={{font=\scriptsize, text=black}},
] table[meta index=2] {{
{chr(10).join(rows)}
}};
\end{{axis}}
\end{{tikzpicture}}
"""
    write_and_compile("figure_4_6_capability_heatmap", tex)


def main() -> None:
    reset_build_dir()
    results = load_results()
    export_tables(results)
    export_bar_charts(results)
    export_question_type_heatmap(results)
    export_capability_radar(results)
    export_capability_heatmap(results)
    print(f"output_dir={OUTPUT_DIR}")


if __name__ == "__main__":
    main()
