
import os
from typing import TypedDict, List, Literal

import cohere
from dotenv import load_dotenv
from pydantic import BaseModel

from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from src.api.v1.tools.tools import TOOLS
from src.core.db import get_sql_agent_db

load_dotenv()

# ─────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────
class AgentState(TypedDict):
    query: str
    route: str

    tool: str
    retrieved_docs: List[dict]
    reranked_docs: List[dict]

    response: dict

    sql_query: str
    sql_result: str

    sub_queries: List[dict]
    final_answer: str


# ─────────────────────────────────────────────────────
# STRUCTURED OUTPUT MODELS
# ─────────────────────────────────────────────────────
class RouteDecision(BaseModel):
    route: Literal["rdbms", "rag", "hybrid"]


class SubQuery(BaseModel):
    type: Literal["sql", "rag"]
    query: str


class HybridOutput(BaseModel):
    sub_queries: List[SubQuery]


# ─────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────
def extract_text(content):
    if isinstance(content, list):
        return " ".join(
            part.get("text", "")
            for part in content if isinstance(part, dict)
        )
    return content or ""


def clean_sql(sql: str) -> str:
    sql = sql.strip()
    if sql.startswith("```"):
        sql = sql.replace("```sql", "").replace("```", "")
    return sql.strip()


def get_llm():
    return ChatGoogleGenerativeAI(
        model=os.getenv("GOOGLE_LLM_MODEL"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0
    )


# ─────────────────────────────────────────────────────
# ROUTER (FIXED)
# ─────────────────────────────────────────────────────
def router_node(state: AgentState) -> AgentState:
    print("\n========== ROUTER ==========")

    llm = get_llm().with_structured_output(RouteDecision)

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         """Classify query:

- rdbms → database query
- rag → informational
- hybrid → both

Return only one."""),
        ("human", "{query}")
    ])

    decision = (prompt | llm).invoke({"query": state["query"]})

    print(f"[router] Route: {decision.route}")

    return {**state, "route": decision.route}


# ─────────────────────────────────────────────────────
# SQL NODE
# ─────────────────────────────────────────────────────
def nl2sql_node(state: AgentState) -> AgentState:
    print("\n========== SQL ==========")

    llm = get_llm()
    db = get_sql_agent_db()
    schema = db.get_table_info()

    prompt = ChatPromptTemplate.from_messages([
        ("system", "Generate PostgreSQL SELECT query only"),
        ("human", "Q: {query}\nSchema:\n{schema}")
    ])

    result = (prompt | llm).invoke({
        "query": state["query"],
        "schema": schema
    })

    sql = clean_sql(extract_text(result.content))
    print(f"[sql] Query: {sql}")

    try:
        sql_result = db.run(sql)
    except Exception as e:
        sql_result = f"Error: {e}"

    print(f"[sql] Result: {str(sql_result)[:200]}")

    summary = extract_text(llm.invoke(f"""
you are a data analyst.

Convert SQL result into a precise answer.

Rules:
- Be concise (1–2 lines)
- Answer based on query intent
- If count → return number clearly
- If list → summarize key values
- If empty → say "No data found"
- Do NOT mention SQL

Query:
{state['query']}

SQL Result:
{sql_result}
""").content)

    return {
        **state,
        "response": {
            "query": state["query"],
            "answer": summary,
            "sql_query": sql,
            "sql_result": str(sql_result)
        }
    }


# ─────────────────────────────────────────────────────
# RAG PIPELINE
# ─────────────────────────────────────────────────────
def planner_node(state: AgentState) -> AgentState:
    return {**state, "tool": "hybrid_search"}


def tool_node(state: AgentState) -> AgentState:
    docs = TOOLS["hybrid_search"](state["query"])
    print(f"[tool] Docs: {len(docs)}")
    return {**state, "retrieved_docs": docs}


def rerank_node(state: AgentState) -> AgentState:
    docs = state["retrieved_docs"]

    if not docs:
        return {**state, "reranked_docs": []}

    co = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))

    res = co.rerank(
        model="rerank-english-v3.0",
        query=state["query"],
        documents=[d["content"] for d in docs],
        top_n=min(3, len(docs))
    )

    return {**state, "reranked_docs": [docs[r.index] for r in res.results]}


def generate_node(state: AgentState) -> AgentState:
    print("\n========== GENERATE ==========")

    llm = get_llm()

    context = "\n\n".join(d["content"] for d in state["reranked_docs"][:3])

    answer = extract_text(llm.invoke(f"""
Summarize context to answer query. provide only the information not extra texts

Context:
{context}

Question:
{state['query']}
""").content)

    return {
        **state,
        "response": {
            "query": state["query"],
            "answer": answer
        }
    }


# ─────────────────────────────────────────────────────
# HYBRID SPLITTER (FIXED)
# ─────────────────────────────────────────────────────
def hybrid_splitter_node(state: AgentState) -> AgentState:
    print("\n========== HYBRID SPLIT ==========")

    llm = get_llm().with_structured_output(HybridOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         """Split query into sub-queries:
- SQL → structured
- RAG → explanation"""),
        ("human", "{query}")
    ])

    result = (prompt | llm).invoke({"query": state["query"]})

    sub_queries = [q.dict() for q in result.sub_queries]

    print(f"[hybrid] {sub_queries}")

    return {**state, "sub_queries": sub_queries}


# ─────────────────────────────────────────────────────
# HYBRID EXECUTOR (FIXED)
# ─────────────────────────────────────────────────────
def hybrid_executor_node(state: AgentState) -> AgentState:
    print("\n========== HYBRID EXEC ==========")

    answers = []

    for sub in state["sub_queries"]:
        q = sub["query"]
        t = sub["type"]

        print(f"[hybrid] → {t}: {q}")

        if t == "sql":
            res = nl2sql_node({**state, "query": q})
            answers.append(res["response"]["answer"])

        else:
            s = planner_node({**state, "query": q})
            s = tool_node(s)
            s = rerank_node(s)
            s = generate_node(s)
            answers.append(s["response"]["answer"])

    return {**state, "final_answer": "\n\n".join(answers)}


# ─────────────────────────────────────────────────────
# HYBRID COMBINER
# ─────────────────────────────────────────────────────
def hybrid_combiner_node(state: AgentState) -> AgentState:
    return {
        **state,
        "response": {
            "query": state["query"],
            "answer": state["final_answer"]
        }
    }


# ─────────────────────────────────────────────────────
# GRAPH
# ─────────────────────────────────────────────────────
def build_agent():
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("sql", nl2sql_node)

    graph.add_node("planner", planner_node)
    graph.add_node("tool", tool_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("generate", generate_node)

    graph.add_node("hybrid_split", hybrid_splitter_node)
    graph.add_node("hybrid_exec", hybrid_executor_node)
    graph.add_node("hybrid_combine", hybrid_combiner_node)

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        lambda s: s["route"],
        {
            "rdbms": "sql",
            "rag": "planner",
            "hybrid": "hybrid_split"
        }
    )

    # SQL
    graph.add_edge("sql", END)

    # RAG
    graph.add_edge("planner", "tool")
    graph.add_edge("tool", "rerank")
    graph.add_edge("rerank", "generate")
    graph.add_edge("generate", END)

    # HYBRID
    graph.add_edge("hybrid_split", "hybrid_exec")
    graph.add_edge("hybrid_exec", "hybrid_combine")
    graph.add_edge("hybrid_combine", END)

    return graph.compile()


agent_graph = build_agent()


# ─────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────
def run_agent(query: str):
    state: AgentState = {
        "query": query,
        "route": "",
        "tool": "",
        "retrieved_docs": [],
        "reranked_docs": [],
        "response": {},
        "sql_query": "",
        "sql_result": "",
        "sub_queries": [],
        "final_answer": ""
    }

    return agent_graph.invoke(state)


















































# import os
# from typing import TypedDict, List, Literal

# import cohere
# from dotenv import load_dotenv
# from pydantic import BaseModel

# from langgraph.graph import StateGraph, END
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_core.prompts import ChatPromptTemplate

# from src.api.v1.tools.tools import TOOLS
# from src.core.db import get_sql_agent_db

# load_dotenv()

# # ─────────────────────────────────────────────────────
# # STATE
# # ─────────────────────────────────────────────────────
# class AgentState(TypedDict):
#     query: str
#     route: str

#     tool: str
#     retrieved_docs: List[dict]
#     reranked_docs: List[dict]

#     response: dict

#     sql_query: str
#     sql_result: str

#     sub_queries: List[dict]
#     final_answer: str


# # ─────────────────────────────────────────────────────
# # STRUCTURED OUTPUT MODELS
# # ─────────────────────────────────────────────────────
# class RouteDecision(BaseModel):
#     route: Literal["rdbms", "rag", "hybrid"]


# class SubQuery(BaseModel):
#     type: Literal["sql", "rag"]
#     query: str


# class HybridOutput(BaseModel):
#     sub_queries: List[SubQuery]


# # ─────────────────────────────────────────────────────
# # HELPERS
# # ─────────────────────────────────────────────────────
# def extract_text(content):
#     if isinstance(content, list):
#         return " ".join(
#             part.get("text", "")
#             for part in content if isinstance(part, dict)
#         )
#     return content or ""


# def clean_sql(sql: str) -> str:
#     sql = sql.strip()
#     if sql.startswith("```"):
#         sql = sql.replace("```sql", "").replace("```", "")
#     return sql.strip()


# def get_llm():
#     return ChatGoogleGenerativeAI(
#         model=os.getenv("GOOGLE_LLM_MODEL"),
#         google_api_key=os.getenv("GOOGLE_API_KEY"),
#         temperature=0
#     )


# # ─────────────────────────────────────────────────────
# # ROUTER (FIXED)
# # ─────────────────────────────────────────────────────
# def router_node(state: AgentState) -> AgentState:
#     print("\n========== ROUTER ==========")

#     llm = get_llm().with_structured_output(RouteDecision)

#     prompt = ChatPromptTemplate.from_messages([
#         ("system",
#          """Classify query:

# - rdbms → database query
# - rag → informational
# - hybrid → both

# Return only one."""),
#         ("human", "{query}")
#     ])

#     decision = (prompt | llm).invoke({"query": state["query"]})

#     print(f"[router] Route: {decision.route}")

#     return {**state, "route": decision.route}


# # ─────────────────────────────────────────────────────
# # SQL NODE
# # ─────────────────────────────────────────────────────
# def nl2sql_node(state: AgentState) -> AgentState:
#     print("\n========== SQL ==========")

#     llm = get_llm()
#     db = get_sql_agent_db()
#     schema = db.get_table_info()

#     prompt = ChatPromptTemplate.from_messages([
#         ("system", "Generate PostgreSQL SELECT query only"),
#         ("human", "Q: {query}\nSchema:\n{schema}")
#     ])

#     result = (prompt | llm).invoke({
#         "query": state["query"],
#         "schema": schema
#     })

#     sql = clean_sql(extract_text(result.content))
#     print(f"[sql] Query: {sql}")

#     try:
#         sql_result = db.run(sql)
#     except Exception as e:
#         sql_result = f"Error: {e}"

#     print(f"[sql] Result: {str(sql_result)[:200]}")

#     summary = extract_text(llm.invoke(f"""
# you are a data analyst.

# Convert SQL result into a precise answer.

# Rules:
# - Be concise (1–2 lines)
# - Answer based on query intent
# - If count → return number clearly
# - If list → summarize key values
# - If empty → say "No data found"
# - Do NOT mention SQL

# Query:
# {state['query']}

# SQL Result:
# {sql_result}
# """).content)

#     return {
#         **state,
#         "response": {
#             "query": state["query"],
#             "answer": summary,
#             "sql_query": sql,
#             "sql_result": str(sql_result)
#         }
#     }


# # ─────────────────────────────────────────────────────
# # RAG PIPELINE
# # ─────────────────────────────────────────────────────
# def planner_node(state: AgentState) -> AgentState:
#     return {**state, "tool": "hybrid_search"}


# def tool_node(state: AgentState) -> AgentState:
#     docs = TOOLS["hybrid_search"](state["query"])
#     print(f"[tool] Docs: {len(docs)}")
#     return {**state, "retrieved_docs": docs}


# def rerank_node(state: AgentState) -> AgentState:
#     docs = state["retrieved_docs"]

#     if not docs:
#         return {**state, "reranked_docs": []}

#     co = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))

#     res = co.rerank(
#         model="rerank-english-v3.0",
#         query=state["query"],
#         documents=[d["content"] for d in docs],
#         top_n=min(3, len(docs))
#     )

#     return {**state, "reranked_docs": [docs[r.index] for r in res.results]}


# def generate_node(state: AgentState) -> AgentState:
#     print("\n========== GENERATE ==========")

#     llm = get_llm()

#     context = "\n\n".join(d["content"] for d in state["reranked_docs"][:3])

#     answer = extract_text(llm.invoke(f"""
# Summarize context to answer query. provide only the information not extra texts

# Context:
# {context}

# Question:
# {state['query']}
# """).content)

#     return {
#         **state,
#         "response": {
#             "query": state["query"],
#             "answer": answer
#         }
#     }


# # ─────────────────────────────────────────────────────
# # HYBRID SPLITTER (FIXED)
# # ─────────────────────────────────────────────────────
# def hybrid_splitter_node(state: AgentState) -> AgentState:
#     print("\n========== HYBRID SPLIT ==========")

#     llm = get_llm().with_structured_output(HybridOutput)

#     prompt = ChatPromptTemplate.from_messages([
#         ("system",
#          """Split query into sub-queries:
# - SQL → structured
# - RAG → explanation"""),
#         ("human", "{query}")
#     ])

#     result = (prompt | llm).invoke({"query": state["query"]})

#     sub_queries = [q.dict() for q in result.sub_queries]

#     print(f"[hybrid] {sub_queries}")

#     return {**state, "sub_queries": sub_queries}


# # ─────────────────────────────────────────────────────
# # HYBRID EXECUTOR (FIXED)
# # ─────────────────────────────────────────────────────
# def hybrid_executor_node(state: AgentState) -> AgentState:
#     print("\n========== HYBRID EXEC ==========")

#     answers = []

#     for sub in state["sub_queries"]:
#         q = sub["query"]
#         t = sub["type"]

#         print(f"[hybrid] → {t}: {q}")

#         if t == "sql":
#             res = nl2sql_node({**state, "query": q})
#             answers.append(res["response"]["answer"])

#         else:
#             s = planner_node({**state, "query": q})
#             s = tool_node(s)
#             s = rerank_node(s)
#             s = generate_node(s)
#             answers.append(s["response"]["answer"])

#     return {**state, "final_answer": "\n\n".join(answers)}


# # ─────────────────────────────────────────────────────
# # HYBRID COMBINER
# # ─────────────────────────────────────────────────────
# def hybrid_combiner_node(state: AgentState) -> AgentState:
#     return {
#         **state,
#         "response": {
#             "query": state["query"],
#             "answer": state["final_answer"]
#         }
#     }


# # ─────────────────────────────────────────────────────
# # GRAPH
# # ─────────────────────────────────────────────────────
# def build_agent():
#     graph = StateGraph(AgentState)

#     graph.add_node("router", router_node)
#     graph.add_node("sql", nl2sql_node)

#     graph.add_node("planner", planner_node)
#     graph.add_node("tool", tool_node)
#     graph.add_node("rerank", rerank_node)
#     graph.add_node("generate", generate_node)

#     graph.add_node("hybrid_split", hybrid_splitter_node)
#     graph.add_node("hybrid_exec", hybrid_executor_node)
#     graph.add_node("hybrid_combine", hybrid_combiner_node)

#     graph.set_entry_point("router")

#     graph.add_conditional_edges(
#         "router",
#         lambda s: s["route"],
#         {
#             "rdbms": "sql",
#             "rag": "planner",
#             "hybrid": "hybrid_split"
#         }
#     )

#     # SQL
#     graph.add_edge("sql", END)

#     # RAG
#     graph.add_edge("planner", "tool")
#     graph.add_edge("tool", "rerank")
#     graph.add_edge("rerank", "generate")
#     graph.add_edge("generate", END)

#     # HYBRID
#     graph.add_edge("hybrid_split", "hybrid_exec")
#     graph.add_edge("hybrid_exec", "hybrid_combine")
#     graph.add_edge("hybrid_combine", END)

#     return graph.compile()


# agent_graph = build_agent()


# # ─────────────────────────────────────────────────────
# # RUN
# # ─────────────────────────────────────────────────────
# def run_agent(query: str):
#     state: AgentState = {
#         "query": query,
#         "route": "",
#         "tool": "",
#         "retrieved_docs": [],
#         "reranked_docs": [],
#         "response": {},
#         "sql_query": "",
#         "sql_result": "",
#         "sub_queries": [],
#         "final_answer": ""
#     }

#     return agent_graph.invoke(state)