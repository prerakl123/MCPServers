import os

OUTPUT_DIR = r"c:\Users\Prerak\PycharmProjects\GMATPrepAI\generated-docs\standalone_prompts"

os.makedirs(OUTPUT_DIR, exist_ok=True)

COMMON_FLOW = """
### COMMON EXECUTION FLOW

1. Use the `search_web` tool to search for context, concepts, or real-world data relevant to the specific GMAT requirement. Use this information to accurately tune the difficulty of the question and use fresh context rather than relying solely on stagnant local knowledge.
2. Formulate and display the generated question along with its options. Follow the GMAT specific option methodology for the section/type requested.
3. Log Timestamp: Execute a tool to write the current timestamp (use `get_current_time` if needed) into the file at exactly:
   `C:\\Users\\Prerak\\PycharmProjects\\GMATPrepAI\\generated-docs\\lm_studio_live_prep_data\\timestamp.txt`
   Overwrite the file if it already exists.
4. Log Question: Execute a tool to append the generated question, options, and the correct choice into the specific file for today. The directory is `C:\\Users\\Prerak\\PycharmProjects\\GMATPrepAI\\generated-docs\\lm_studio_live_prep_data\\question_data`. 
   The filename should be formatted as `{section}_{specific_topic}_{date}.txt`.
   Use exactly this format to append:
   
   {Section} | {Specific Topic/Skill/Domain/etc. whichever is focussed on separated by `|`}
   {Question}
   {Choices}
   {Correct Choice}
   
   **CRITICAL: DO NOT INCLUDE ANY EXPLANATIONS AT ALL. NOWHERE.**
5. Pause and wait for the user to provide their answer input.
6. After User Input:
   - Check the timestamp previously written in `timestamp.txt`.
   - Calculate the elapsed time taken by the user by comparing it with the current live time.
   - Append the timing information and a separator line to the questions file (the same file used in step 4) in exactly the following format:
   
   {start_timestamp} | {end_timestamp} | {elapsed time}
   =====

7. Repeat the entire process from Step 1 (search web -> question -> timestamp -> log question -> wait for user answer -> log time -> repeat).
"""

SECTIONS = {
    "QUANT": ("Quantitative Reasoning", "Options Methodology: Provide 5 standard multiple-choice options (A, B, C, D, E). The options must consist of unambiguous mathematical values or algebraic expressions."),
    "VERBAL": ("Verbal Reasoning", "Options Methodology: Provide 5 standard multiple-choice options (A, B, C, D, E). Options should be plausible statements that test logical deduction or reading comprehension."),
    "DI": ("Data Insights", "Options Methodology: Depending on the specific format, provide Data Sufficiency options (Standard 5 choices about statement sufficiency), Two-Part Analysis (2 columns to select from 5-6 choices), Multi-Source Reasoning (Yes/No or Multiple Choice based on multiple text/data sources), or Graphs and Tables (Dropdown style fill-in-the-blanks).")
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

def write_prompt(filename, title, section, specific_topic, methodology):
    content = f"# GMAT Prompt Flow: {title}\n\n"
    content += f"## Context\n"
    content += f"You are an AI acting as a live GMAT prep tutor. You are testing the user specifically on:\n"
    content += f"- Section: {section}\n"
    content += f"- Focus Topic: {specific_topic}\n\n"
    content += f"## Options Methodology\n{methodology}\n\n"
    content += COMMON_FLOW
    
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

# 1. Section prompts
for key, (name, methodology) in SECTIONS.items():
    write_prompt(f"prompt_section_{key.lower()}.txt", name, name, "All topics in this section", methodology)

# 2. Type distributions
for key, (sec_key, name) in TYPES.items():
    sec_name, methodology = SECTIONS[sec_key]
    write_prompt(f"prompt_type_{key.lower()}.txt", f"{sec_name} - {name}", sec_name, f"Question Type: {name}", methodology)

# 3. Domain distributions
for key, (sec_key, name) in DOMAINS.items():
    sec_name, methodology = SECTIONS[sec_key]
    write_prompt(f"prompt_domain_{key.lower()}.txt", f"{sec_name} - {name}", sec_name, f"Content Domain: {name}", methodology)

# 4. Skill distributions
for key, (sec_key, name) in SKILLS.items():
    sec_name, methodology = SECTIONS[sec_key]
    write_prompt(f"prompt_skill_{key.lower()}.txt", f"{sec_name} - {name}", sec_name, f"Fundamental Skill: {name}", methodology)

print("Prompts generated successfully.")
