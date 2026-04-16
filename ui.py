
# import streamlit as st
# import requests
# import pandas as pd
# import os

# # -------------------------
# # CONFIG
# # -------------------------
# BASE_URL = "http://localhost:8000"
# QUERY_API = f"{BASE_URL}/api/v1/query"
# UPLOAD_API = f"{BASE_URL}/api/v1/admin/upload"

# ADMIN_PASSWORD = "admin123"

# st.set_page_config(page_title="Smart Banking Assistant", layout="wide")

# # -------------------------
# # SESSION STATE
# # -------------------------
# if "messages" not in st.session_state:
#     st.session_state.messages = []

# if "admin_logged_in" not in st.session_state:
#     st.session_state.admin_logged_in = False

# if "uploading" not in st.session_state:
#     st.session_state.uploading = False

# # -------------------------
# # SIDEBAR
# # -------------------------
# with st.sidebar:
#     st.title("Controls")

#     if st.button("Clear Chat"):
#         st.session_state.messages = []
#         st.rerun()

#     st.divider()

#     st.subheader("Admin Panel")

#     if not st.session_state.admin_logged_in:
#         password = st.text_input("Enter Password", type="password")

#         if st.button("Login"):
#             if password == ADMIN_PASSWORD:
#                 st.session_state.admin_logged_in = True
#                 st.success("Logged in")
#                 st.rerun()
#             else:
#                 st.error("Wrong password")

#     else:
#         st.success("Admin Logged In")

#         uploaded_file = st.file_uploader(
#             "Upload file for ingestion",
#             type=["pdf", "txt"]
#         )

#         if uploaded_file:
#             if st.button("Upload & Ingest", disabled=st.session_state.uploading):
#                 st.session_state.uploading = True

#                 with st.spinner("Uploading and processing..."):
#                     try:
#                         res = requests.post(
#                             UPLOAD_API,
#                             files={"file": uploaded_file}
#                         )

#                         if res.status_code == 200:
#                             data = res.json()
#                             st.success("File ingested successfully!")
#                             st.info(f"Chunks created: {data.get('chunks_created', 0)}")
#                         else:
#                             st.error(f"Upload failed: {res.text}")

#                     except Exception as e:
#                         st.error(f"Error: {str(e)}")

#                 st.session_state.uploading = False

# # -------------------------
# # MAIN TITLE
# # -------------------------
# st.title("Smart Banking Assistant")

# # -------------------------
# # DISPLAY CHAT HISTORY
# # -------------------------
# for i, msg in enumerate(st.session_state.messages):
#     with st.chat_message(msg["role"]):

#         if msg["role"] == "user":
#             st.markdown(msg["content"])

#         else:
#             # Show answer always
#             st.markdown(msg.get("content", ""))

#             # 🔥 Instant toggle (radio = faster)
#             view = st.radio(
#                 "View",
#                 ["Answer", "Chunks", "Query"],
#                 horizontal=True,
#                 key=f"view_{i}"
#             )

#             # -------------------------
#             # VIEW SWITCH
#             # -------------------------
#             if view == "Chunks":
#                 chunks = msg.get("chunks", [])

#                 if chunks:
#                     for idx, chunk in enumerate(chunks[:3]):  # limit for speed
#                         with st.expander(f"Chunk {idx+1}", expanded=False):
#                             st.write(chunk.get("content", ""))
#                 else:
#                     st.info("No chunks available")

#             elif view == "Query":
#                 st.text(msg.get("query", ""))

#             # -------------------------
#             # IMAGE DISPLAY
#             # -------------------------
#             image_path = msg.get("image_path")

#             if image_path:
#                 st.divider()
#                 if os.path.exists(image_path):
#                     st.image(image_path, use_column_width=True)

#             # -------------------------
#             # SQL DISPLAY
#             # -------------------------
#             if msg.get("sql_query"):
#                 with st.expander("SQL Query"):
#                     st.code(msg["sql_query"], language="sql")

#             if msg.get("sql_result"):
#                 with st.expander("SQL Result"):
#                     try:
#                         df = pd.DataFrame(eval(msg["sql_result"]))
#                         st.dataframe(df)
#                     except:
#                         st.text(msg["sql_result"])

# # -------------------------
# # USER INPUT
# # -------------------------
# query = st.chat_input("Ask your question...")

# if query:
#     # Add user message
#     st.session_state.messages.append({
#         "role": "user",
#         "content": query
#     })

#     with st.chat_message("user"):
#         st.markdown(query)

#     # Assistant response
#     with st.chat_message("assistant"):
#         with st.spinner("Thinking..."):
#             try:
#                 response = requests.post(
#                     QUERY_API,
#                     json={"query": query}
#                 )

#                 if response.status_code == 200:
#                     data = response.json()

#                     answer = data.get("answer", "No answer found")
#                     chunks = data.get("retrieved_results", [])
#                     sql_query = data.get("sql_query")
#                     sql_result = data.get("sql_result")
#                     image_path = data.get("image_path")

#                     # Show answer immediately
#                     st.markdown(answer)

#                     # 🔥 Instant toggle for new response
#                     view = st.radio(
#                         "View",
#                         ["Answer", "Chunks", "Query"],
#                         horizontal=True,
#                         key=f"view_new_{len(st.session_state.messages)}"
#                     )

#                     if view == "Chunks":
#                         if chunks:
#                             for idx, chunk in enumerate(chunks[:3]):
#                                 with st.expander(f"Chunk {idx+1}"):
#                                     st.write(chunk.get("content", ""))
#                         else:
#                             st.info("No chunks available")

#                     elif view == "Query":
#                         st.text(query)

#                     # Image
#                     if image_path and os.path.exists(image_path):
#                         st.image(image_path, use_column_width=True)

#                     # SQL
#                     if sql_query:
#                         with st.expander("SQL Query"):
#                             st.code(sql_query, language="sql")

#                     if sql_result:
#                         with st.expander("SQL Result"):
#                             try:
#                                 df = pd.DataFrame(eval(sql_result))
#                                 st.dataframe(df)
#                             except:
#                                 st.text(sql_result)

#                     # Save message
#                     st.session_state.messages.append({
#                         "role": "assistant",
#                         "content": answer,
#                         "chunks": chunks,
#                         "query": query,
#                         "sql_query": sql_query,
#                         "sql_result": sql_result,
#                         "image_path": image_path
#                     })

#                 else:
#                     st.error(f"API Error: {response.text}")

#             except Exception as e:
#                 st.error(f"Error: {str(e)}")

import streamlit as st
import requests
import pandas as pd
import os
import ast

# -------------------------
# CONFIG
# -------------------------
BASE_URL = "http://localhost:8000"
QUERY_API = f"{BASE_URL}/api/v1/query"
UPLOAD_API = f"{BASE_URL}/api/v1/admin/upload"

ADMIN_PASSWORD = "admin123"

st.set_page_config(page_title="Smart Banking Assistant", layout="wide")

# -------------------------
# SESSION STATE
# -------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if "uploading" not in st.session_state:
    st.session_state.uploading = False


# -------------------------
# HELPER FUNCTION
# -------------------------
def render_assistant_response(msg, idx=None):
    """
    Renders assistant response:
    - Answer
    - Query
    - Retrieved chunks in dropdowns
    - SQL query/result
    - Image (if any)
    """

    # -------------------------
    # ANSWER
    # -------------------------
    st.markdown(msg.get("content", ""))

    # -------------------------
    # QUERY
    # -------------------------
    query_text = msg.get("query")
    if query_text:
        st.markdown("### Query")
        st.code(query_text, language="text")

    # -------------------------
    # RETRIEVED CHUNKS
    # -------------------------
    chunks = msg.get("chunks", [])
    if chunks:
        st.markdown("### Retrieved Chunks")

        for chunk_idx, chunk in enumerate(chunks, start=1):
            chunk_type = chunk.get("chunk_type", "N/A")
            page = chunk.get("page", "N/A")
            section = chunk.get("section", "N/A")
            source = chunk.get("source", "N/A")
            similarity = chunk.get("similarity", "N/A")
            created_date = chunk.get("created_date", "N/A")
            content = chunk.get("content", "")

            expander_title = f"Chunk {chunk_idx} | {chunk_type} | Page {page} | Similarity: {similarity}"

            with st.expander(expander_title, expanded=False):
                st.markdown("#### Metadata")
                st.markdown(f"**chunk_type:** {chunk_type}")
                st.markdown(f"**page:** {page}")
                st.markdown(f"**section:** {section}")
                st.markdown(f"**source:** {source}")
                st.markdown(f"**similarity:** {similarity}")
                st.markdown(f"**created_date:** {created_date}")

                st.markdown("#### Content")
                st.write(content)
    else:
        st.info("No retrieved chunks available")

    # -------------------------
    # IMAGE DISPLAY
    # -------------------------
    image_path = msg.get("image_path")
    if image_path:
        st.divider()
        if os.path.exists(image_path):
            st.image(image_path, use_container_width=True)

    # -------------------------
    # SQL DISPLAY
    # -------------------------
    if msg.get("sql_query"):
        with st.expander("SQL Query"):
            st.code(msg["sql_query"], language="sql")

    if msg.get("sql_result"):
        with st.expander("SQL Result"):
            try:
                parsed_result = ast.literal_eval(msg["sql_result"])
                df = pd.DataFrame(parsed_result)
                st.dataframe(df, use_container_width=True)
            except Exception:
                st.text(msg["sql_result"])


# -------------------------
# SIDEBAR
# -------------------------
with st.sidebar:
    st.title("Controls")

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    st.subheader("Admin Panel")

    if not st.session_state.admin_logged_in:
        password = st.text_input("Enter Password", type="password")

        if st.button("Login"):
            if password == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.success("Logged in")
                st.rerun()
            else:
                st.error("Wrong password")

    else:
        st.success("Admin Logged In")

        uploaded_file = st.file_uploader(
            "Upload file for ingestion",
            type=["pdf", "txt"]
        )

        if uploaded_file:
            if st.button("Upload & Ingest", disabled=st.session_state.uploading):
                st.session_state.uploading = True

                with st.spinner("Uploading and processing..."):
                    try:
                        res = requests.post(
                            UPLOAD_API,
                            files={"file": uploaded_file}
                        )

                        if res.status_code == 200:
                            data = res.json()
                            st.success("File ingested successfully!")
                            st.info(f"Chunks created: {data.get('chunks_created', 0)}")
                        else:
                            st.error(f"Upload failed: {res.text}")

                    except Exception as e:
                        st.error(f"Error: {str(e)}")

                st.session_state.uploading = False


# -------------------------
# MAIN TITLE
# -------------------------
st.title("Smart Banking Assistant")


# -------------------------
# DISPLAY CHAT HISTORY
# -------------------------
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            render_assistant_response(msg, idx=i)


# -------------------------
# USER INPUT
# -------------------------
query = st.chat_input("Ask your question...")

if query:
    # Add user message
    st.session_state.messages.append({
        "role": "user",
        "content": query
    })

    with st.chat_message("user"):
        st.markdown(query)

    # Assistant response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    QUERY_API,
                    json={"query": query}
                )

                if response.status_code == 200:
                    data = response.json()

                    answer = data.get("answer", "No answer found")
                    chunks = data.get("retrieved_results", [])
                    sql_query = data.get("sql_query")
                    sql_result = data.get("sql_result")
                    image_path = data.get("image_path")
                    returned_query = data.get("query", query)

                    assistant_msg = {
                        "role": "assistant",
                        "content": answer,
                        "chunks": chunks,
                        "query": returned_query,
                        "sql_query": sql_query,
                        "sql_result": sql_result,
                        "image_path": image_path
                    }

                    # Render immediately
                    render_assistant_response(assistant_msg)

                    # Save to session
                    st.session_state.messages.append(assistant_msg)

                else:
                    st.error(f"API Error: {response.text}")

            except Exception as e:
                st.error(f"Error: {str(e)}")
