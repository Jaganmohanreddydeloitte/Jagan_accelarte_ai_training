# Recovery Prompts — IDAMP Troubleshooting Guide

**What is this?** When something goes wrong, copy the appropriate prompt below, fill in your specific error/problem, and paste it to get help. These prompts are designed to provide enough context for quick, accurate solutions.

---

## Recovery Prompt A: Decoding Error Messages

**Use this when:** You see an error message and don't understand what it means.

```
I got this error message: [PASTE ERROR HERE]. 

I am a beginner building an AI data pipeline with Python, LangChain, and Streamlit. 
Explain what this error means in simple English and give me the exact steps to fix it. 
Do not assume I know anything. 

Show me:
1. What the error means
2. Which file to open
3. What line to look at
4. The exact code to fix it
5. How to verify the fix worked
```

**Example of good error to paste:**
```
ModuleNotFoundError: No module named 'langchain_groq'

Traceback (most recent call last):
  File "C:\Users\...\agents\profiler.py", line 5, in <module>
    from langchain_groq import ChatGroq
ModuleNotFoundError: No module named 'langchain_groq'
```

---

## Recovery Prompt B: Wrong Output / Wrong Behavior

**Use this when:** Code runs without crashing, but does the wrong thing.

```
The code you gave me is not working as expected.

The file is: [FILE NAME]

It is supposed to do: [DESCRIBE WHAT IT SHOULD DO]

But instead it does: [DESCRIBE WHAT IT ACTUALLY DOES]

Please:
1. Explain what went wrong
2. Rewrite the entire file from scratch with the correct implementation
3. Explain the changes you made
4. Tell me how to test that it works now
```

**Example of good problem to paste:**
```
The file is: agents/bronze_agent.py

It is supposed to do: Read Bronze STTM CSV rules and apply them to input Parquet files to transform column names and add metadata.

But instead it does: Reads the STTM CSV but applies ALL rules to ALL input files, even if the rule source_column doesn't exist in that file. This causes a KeyError crash instead of gracefully handling the missing column.
```

---

## Recovery Prompt C: Lost and Confused

**Use this when:** You're not sure what to do next or where you are in the project.

```
I am lost and confused while building my AI data pipeline project. 
Here is what I have done so far:

Files I have created:
[LIST YOUR FILES]

Current error or problem:
[DESCRIBE THE ISSUE]

What I am trying to do next:
[DESCRIBE NEXT STEP]

Please guide me step by step like I have never coded before. Tell me:
1. Exactly what to do next
2. What commands to run
3. What to type in each file
4. How to verify each step worked
```

**Example of good context to paste:**
```
Files I have created:
- core/config.py
- core/audit.py
- core/observability.py
- core/state.py
- agents/profiler.py
- agents/bronze_agent.py

Current error or problem:
I'm not sure if my imports are working. When I run test_import.py, it fails on line 24.

What I am trying to do next:
I want to make sure core/config.py is loading environment variables correctly from .env file before I build more agents.
```

---

## Recovery Prompt D: Missing Dependencies / Import Errors

**Use this when:** You see `ModuleNotFoundError` or `ImportError`.

```
I am getting a "ModuleNotFoundError" or "ImportError" when running my Python code.

The error says: [PASTE ERROR]

I am in a virtual environment (venv). Please tell me:
1. What package I need to install
2. The exact pip install command
3. How to verify it installed correctly
4. If there are any version compatibility issues to watch for
```

**Example of good error to paste:**
```
The error says: ModuleNotFoundError: No module named 'streamlit'

When I run: python -m pytest tests/test_audit.py

I am in a virtual environment (venv).
```

---

## Recovery Prompt E: API Key Issues

**Use this when:** You get authentication errors from LLM APIs.

```
I am getting an API key error when my AI agents try to run.

The error says: [PASTE ERROR]

I am trying to use: [GROQ / GOOGLE / OPENAI / GITHUB]

Please help me:
1. Understand what went wrong
2. Find where to get the correct API key
3. How to properly set it in my .env file
4. How to verify the API key is working
```

**Example of good error to paste:**
```
The error says: groq.error.AuthenticationError: Invalid API key provided.

I am trying to use: GROQ

My .env file has:
GROQ_API_KEY=gsk_abc123def456

But I'm not sure if this is the right format.
```

---

## Recovery Prompt F: Groq Model / Reasoning / Stale Process Issues

**Use this when:** STTM files are empty, same error happens after you fix it, or Groq returns `model_not_found`.

```
My pipeline ran without a Python error, but something still looks wrong — for example:
- The Bronze/Silver/Gold STTM file is empty or corrupted
- I fixed something but the exact same failure happens again on the next run
- A Groq call fails with "model_not_found" or the model works sometimes but returns strange/empty content

I am a beginner building an AI data pipeline with Python, LangChain(-Groq), and Streamlit. 
Please walk me through:

1. Confirm the actual GROQ_MODEL being used at runtime (print it from core/config.py) and compare it to
   what's in my .env file — is it being read from the environment, or hardcoded somewhere?

2. If I'm using a Groq "reasoning" model (anything with "gpt-oss" or reasoning capability), check whether
   `reasoning_format="hidden"` is passed everywhere ChatGroq is constructed, so hidden chain-of-thought
   `<think>...</think>` text doesn't leak into `response.content` and break JSON parsing.

3. Check the actual trace/audit files for the failing run (data/traces/*.json, audit_logs/*.jsonl) to see 
   the RAW text the LLM returned, not just the summarized "success" message — agents can hallucinate a
   confident-looking summary even when the underlying tool call actually failed or returned nothing useful.

4. Check for duplicate/stale server processes still bound to the same port with old code loaded, using:
   Windows:
   ```powershell
   Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='streamlit.exe'" | Select-Object ProcessId, CommandLine
   ```
   
   macOS/Linux:
   ```bash
   lsof -i :8501
   ```
   
   Kill any stray ones, then restart exactly one clean process before concluding a fix "didn't work".

5. Tell me the exact code fix and how to verify it worked using the trace/audit files, not just "no error shown".
```

**Example of good problem to paste:**
```
My pipeline ran without a Python error, but:
- The Bronze/Silver/Gold STTM file is empty or corrupted

Error details:
When I complete Phase 1, the bronze_sttm_*.csv file has 0 bytes. 
Streamlit shows: EmptyDataError: No columns to parse from file
Terminal shows no Python traceback, just a quiet failure.

I checked .env and it has:
GROQ_MODEL=llama-3.3-70b-versatile

I tried restarting Streamlit but got the exact same error again.
```

---

## When to Use Each Prompt

| Situation | Use This | Why |
|-----------|----------|-----|
| You see a Python error with traceback | **Prompt A** | Shows file, line, exact error — need direct explanation |
| Code runs but gives wrong result | **Prompt B** | Need full rewrite with explanation |
| You're not sure what to do | **Prompt C** | Need step-by-step beginner guidance |
| ModuleNotFoundError or ImportError | **Prompt D** | Common pip/venv issue — need install help |
| Groq/OpenAI/Google auth fails | **Prompt E** | API key issue — need setup help |
| STTM empty, same error after fix, or model_not_found | **Prompt F** | Subtle issues: env vars, reasoning models, stale processes |

---

## Tips for Getting Help Faster

1. **Copy the entire error message** — Don't summarize, include the full traceback
2. **Describe what you expected** — "It should do X" helps catch logic bugs
3. **Describe what actually happened** — "But it did Y instead"
4. **Include your .env file** — (REMOVE ACTUAL KEYS first!) Show which keys are set
5. **Include file names** — Help narrow down which module is failing
6. **Describe your environment** — Python version, OS (Windows/Mac/Linux), venv status
7. **Show command you ran** — `python test_import.py` vs `pytest tests/` vs `streamlit run app/streamlit_app.py`

---

## Before Asking for Help: Self-Diagnosis Checklist

Try these first:

### For Any Error
- [ ] Is your virtual environment activated? (Prompt shows `(venv)`)
- [ ] Did you run `pip install -r requirements.txt` after activating venv?
- [ ] Is your `.env` file in the project root with all API keys filled?
- [ ] Did you run `python test_import.py` to check imports?
- [ ] Are there stale Python processes running? (See Prompt F)

### For Module/Import Errors
- [ ] Did you spell the file/module name correctly?
- [ ] Is the file in the right folder (`core/`, `agents/`, `app/`)?
- [ ] Does the module have an `__init__.py` file?
- [ ] Did you reinstall dependencies: `pip install --force-reinstall -r requirements.txt`?

### For API Key Errors
- [ ] Is the API key pasted EXACTLY (no extra spaces)?
- [ ] Did you restart Streamlit after updating `.env`?
- [ ] Is the API key for the right service (Groq != OpenAI != Google)?
- [ ] Can you test the key manually with a quick Python script?

### For Groq Errors
- [ ] Check the model name at https://console.groq.com/docs/models — is it still valid?
- [ ] Update `.env` if the model name changed
- [ ] Restart Streamlit after updating `.env`
- [ ] Is `reasoning_format="hidden"` set in `agents/sttm_generator.py`?
- [ ] Kill all stale Python processes and restart (Prompt F step 4)

### For "Same Error After Fixing" Issues
- [ ] Kill all stale Python processes (Prompt F step 4)
- [ ] Clear Streamlit cache: `rm -rf ~/.streamlit/cache` (macOS/Linux) or delete `%USERPROFILE%\.streamlit\cache` (Windows)
- [ ] Verify your code change was actually saved
- [ ] Restart Streamlit fresh in a new terminal
- [ ] Check `data/traces/` and `data/audit_logs/` to see what the agent actually did vs. what you think it did

---

## How to Copy & Paste These Prompts

1. Pick the recovery prompt that matches your problem (A-F above)
2. Copy the entire prompt text (everything in the ``` code block)
3. Paste it to an AI assistant, code reviewer, or forum
4. Fill in the bracketed sections [LIKE THIS] with your specific details
5. Keep the full prompt format — it provides important context

---

## Example: Putting It All Together

**Bad question:**
```
My code doesn't work. Can you help?
```

**Good question using Prompt D:**
```
I am getting a "ModuleNotFoundError" or "ImportError" when running my Python code.

The error says: 
ModuleNotFoundError: No module named 'langchain'
  File "agents/profiler.py", line 5, in <module>
    from langchain_google_genai import ChatGoogleGenerativeAI

I am in a virtual environment (venv). Please tell me:
1. What package I need to install
2. The exact pip install command
3. How to verify it installed correctly
4. If there are any version compatibility issues to watch for
```

**Result:** Clear, specific, includes error, includes file name, includes module name → Fast answer

---

## Additional Resources

If none of these prompts fit your problem:

1. **README.md** — General overview, setup, FAQ
2. **SETUP_CHECKLIST.md** — Detailed troubleshooting flowchart and common fixes
3. **tests/README.md** — Testing guide with pytest examples
4. **data/traces/*.json** — Raw agent reasoning for that run
5. **data/audit_logs/*.jsonl** — Chronological log of all actions

---

**Remember:** The more context and detail you provide, the faster and better the answer will be! 🚀
