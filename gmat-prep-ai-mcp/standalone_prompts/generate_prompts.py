import os

OUTPUT_DIR = r"C:\Users\Prerak\MCPServers\gmat-prep-ai-mcp\standalone_prompts"
LOG_DIR = r"C:\Users\Prerak\AppData\Local\GMATPrepAI\logs"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_common_flow(log_dir):
    return f"""
### COMMON EXECUTION FLOW

1. Use the `search_web` tool to search for context, concepts, or real-world data relevant to the specific GMAT requirement. Use this information to accurately tune the difficulty of the question and use fresh context rather than relying solely on stagnant local knowledge.
2. Formulate and display the generated question along with its options. STRICTLY follow the Options Methodology defined above.
3. Log Timestamp: Execute a tool to write the current timestamp (use `get_current_time` if needed) into the file at exactly:
   `{log_dir}\\timestamp.txt`
   Overwrite the file if it already exists. (Ensure the directory is created if it does not exist).
   The timezone is IST (India Standard Time).
4. Log Question: Execute a tool to append the generated question, options, and the correct choice into the specific file for today. The directory is `{log_dir}\\question_data`. 
   The filename should be formatted as `{{section}}_{{specific_topic}}_{{date}}.txt`.
   Use exactly this format to append:

   {{Section}} | {{Specific Topic/Skill/Domain/etc. whichever is focussed on separated by `|`}}
   {{Question}}
   {{Choices}}
   {{Correct Choice}}

   **CRITICAL: DO NOT INCLUDE ANY EXPLANATIONS AT ALL. NOWHERE.**
5. Pause and wait for the user to provide their answer input. If the user does not provide an input within 60 seconds, end your generation and let the user take time.
6. After User Input:
   - Check the timestamp previously written in `timestamp.txt`.
   - Calculate the elapsed time taken by the user by comparing it with the current live time.
   - Append the timing information and a separator line to the questions file (the same file used in step 4) in exactly the following format:

   {{start_timestamp}} | {{end_timestamp}} | {{elapsed time}}
   =====

7. Repeat the entire process from Step 1 (search web -> question -> timestamp -> log question -> wait for user answer -> log time -> repeat).
8. IMPORTANT: The timestamp file and the questions file are separate entities. The timestamp file should ALWAYS be less than 1 KB in size. It should contain only the timestamp and nothing else. It will be overwritten in every run. The questions file will be appended in every run.
   If the questions file is not found, create it and append the first question to it. If the file already exists, append the question to it. If the directory containing the questions file does not exist, create it.
"""


SECTIONS = {
    "QUANT": "Quantitative Reasoning",
    "VERBAL": "Verbal Reasoning",
    "DI": "Data Insights"
}

# The base methodologies
METHODOLOGIES = {
    "QUANT": "Provide 5 standard multiple-choice options (A, B, C, D, E). The options must consist of unambiguous mathematical values or algebraic expressions. Provide exactly ONE correct answer.",
    "VERBAL": "Provide 5 standard multiple-choice options (A, B, C, D, E). Options should be plausible statements that test logical deduction or reading comprehension. Provide exactly ONE correct answer.",
    "DI": "Format depends on the specific Data Insights question type (DS, MSR, TPA, or GT). Make sure to format options appropriately based on the requested type."
}

# Specific overrides/additions
SPECIFICS = {
    "DI_DS": "For Data Sufficiency, the options A-E are FIXED and MUST never be changed:\nA. Statement (1) ALONE is sufficient, but statement (2) alone is not sufficient.\nB. Statement (2) ALONE is sufficient, but statement (1) alone is not sufficient.\nC. BOTH statements TOGETHER are sufficient, but NEITHER statement ALONE is sufficient.\nD. EACH statement ALONE is sufficient.\nE. Statements (1) and (2) TOGETHER are NOT sufficient.",
    "DI_MSR": "For Multi-Source Reasoning, present the information as different 'tabs' corresponding to the real GMAT. Since true tabs cannot be rendered in chat, simulate them by writing down the passage, tables, or diagrams for each tab clearly segregated and separated by horizontal lines (`---`). Then provide 3 dichotomous choices (e.g., Yes/No) or a standard multiple-choice question based on all tabs.",
    "DI_TPA": "For Two-Part Analysis, present a scenario followed by a table with 2 columns to select from and 5-6 row choices. The user must be able to select one choice per column.",
    "DI_GT": "For Graphs and Tables, present a graph or table (using markdown or ASCII art). Then provide a short paragraph with 2 fill-in-the-blank dropdowns. Each dropdown should have 3-5 options.",
    "Q_PURE_CONTEXT": "For Pure Context Quantitative questions, focus on abstract math without real-world storytelling. Provide 5 standard A-E options.",
    "Q_REAL_CONTEXT": "For Real Context Quantitative questions, focus on word problems using real-world scenarios. Provide 5 standard A-E options.",
    "V_CR": "For Critical Reasoning, provide a short stimulus paragraph, a question stem, and exactly 5 choices (A-E). Focus on logical flaws, assumptions, strengthening, or weakening arguments.",
    "V_RC": "For Reading Comprehension, provide a passage (200-400 words) followed by a question. Provide exactly 5 choices (A-E). Ensure the options test inference, main idea, or specific details."
}

DOMAINS = {
    "Q_ARITHMETIC": ("QUANT", "Arithmetic"),
    "Q_ALGEBRA": ("QUANT", "Algebra"),
    "DI_MATH": ("DI", "Math Related"),
    "DI_NON_MATH": ("DI", "Non-Math Related")
}

TYPES = {
    "Q_PURE_CONTEXT": ("QUANT", "Pure Context (abstract math)"),
    "Q_REAL_CONTEXT": ("QUANT", "Real Context (word problems)"),
    "V_CR": ("VERBAL", "Critical Reasoning"),
    "V_RC": ("VERBAL", "Reading Comprehension"),
    "DI_DS": ("DI", "Data Sufficiency"),
    "DI_GT": ("DI", "Graphs and Tables"),
    "DI_MSR": ("DI", "Multi-Source Reasoning"),
    "DI_TPA": ("DI", "Two-Part Analysis")
}

SKILLS = {
    "Q_RATES_RATIOS_PERCENT": ("QUANT", "Rates, Ratios and Percentages"),
    "Q_VALUE_ORDER_FACTORS": ("QUANT", "Value, Order and Factors"),
    "Q_EQUAL_UNEQUAL_ALG": ("QUANT", "Equalities, Inequalities and Algebra"),
    "Q_COUNTING_SETS_SERIES": ("QUANT", "Counting, Sets, Series, Probability and Statistics"),
    "V_ANALYSIS_CRITIQUE": ("VERBAL", "Analysis and Critique"),
    "V_PLAN_CONSTRUCT": ("VERBAL", "Plan and Construct"),
    "V_IDENTIFY_INFERRED": ("VERBAL", "Identify Inferred Idea"),
    "V_IDENTIFY_STATED": ("VERBAL", "Identify Stated Idea")
}


def get_methodology(key, sec_key):
    base = METHODOLOGIES.get(sec_key, "")
    specific = SPECIFICS.get(key, "")
    if specific:
        return f"{base}\n\n**Specific Requirements for {key}:**\n{specific}"
    else:
        return f"{base}"


def write_prompt(filename, title, section, specific_topic, methodology):
    content = f"# GMAT Prompt Flow: {title}\n\n"
    content += f"## Context\n"
    content += f"You are an AI acting as a live GMAT prep tutor. You are testing the user specifically on:\n"
    content += f"- Section: {section}\n"
    content += f"- Focus Topic: {specific_topic}\n\n"
    content += f"## Options Methodology\n{methodology}\n\n"
    content += get_common_flow(LOG_DIR)

    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


# 1. Section prompts
for key, name in SECTIONS.items():
    write_prompt(f"prompt_section_{key.lower()}.txt", name, name, "All topics in this section",
                 get_methodology(key, key))

# 2. Type distributions
for key, (sec_key, name) in TYPES.items():
    sec_name = SECTIONS[sec_key]
    write_prompt(f"prompt_type_{key.lower()}.txt", f"{sec_name} - {name}", sec_name, f"Question Type: {name}",
                 get_methodology(key, sec_key))

# 3. Domain distributions
for key, (sec_key, name) in DOMAINS.items():
    sec_name = SECTIONS[sec_key]
    write_prompt(f"prompt_domain_{key.lower()}.txt", f"{sec_name} - {name}", sec_name, f"Content Domain: {name}",
                 get_methodology(key, sec_key))

# 4. Skill distributions
for key, (sec_key, name) in SKILLS.items():
    sec_name = SECTIONS[sec_key]
    write_prompt(f"prompt_skill_{key.lower()}.txt", f"{sec_name} - {name}", sec_name, f"Fundamental Skill: {name}",
                 get_methodology(key, sec_key))

print("Prompts generated successfully.")
