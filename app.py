import streamlit as st
import pandas as pd
from datetime import datetime
from io import StringIO
from streamlit_gsheets import GSheetsConnection

# ---------- CONFIG ----------
st.set_page_config(
    page_title="Grocery List Manager",
    layout="centered",
)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1bNv-LBZ3jLURJIHGJbqlMxaR8JXHaZsgTekLXtlu4dE/edit?usp=sharing"
#  https://docs.google.com/spreadsheets/d/1bNv-LBZ3jLURJIHGJbqlMxaR8JXHaZsgTekLXtlu4dE/edit#gid=0"
# Replace with your real sheet URL

# ---------- HELPERS ----------

@st.cache_data(ttl=60)
def load_data(conn: GSheetsConnection) -> pd.DataFrame:
    df = conn.read(spreadsheet=SHEET_URL)
    if df is None or df.empty:
        df = pd.DataFrame(
            columns=[
                "Date Added",
                "Item Needed",
                "Quantity",
                "Where to Get",
                "Urgency",
                "Completed",
            ]
        )
    # Ensure column types
    if "Completed" in df.columns:
        df["Completed"] = df["Completed"].fillna(False).astype(bool)
    return df


def save_data(conn: GSheetsConnection, df: pd.DataFrame) -> None:
    # Ensure all columns exist and types are sane
    for col in [
        "Date Added",
        "Item Needed",
        "Quantity",
        "Where to Get",
        "Urgency",
        "Completed",
    ]:
        if col not in df.columns:
            df[col] = "" if col != "Completed" else False

    conn.update(spreadsheet=SHEET_URL, data=df)


def styled_urgency(df: pd.DataFrame) -> pd.DataFrame:
    # For display only: add an emoji+label version
    def fmt(u):
        if u == "Now":
            return "🔴 Now"
        elif u == "Soon":
            return "🟡 Soon"
        elif u == "Yesterday!":
            return "🟣 Yesterday!"
        return u or ""

    display_df = df.copy()
    display_df["Urgency"] = display_df["Urgency"].apply(fmt)
    return display_df


# ---------- CONNECTION ----------
conn = st.connection("gsheets", type=GSheetsConnection)

# ---------- SESSION STATE ----------
if "df" not in st.session_state:
    st.session_state.df = load_data(conn)

# ---------- SIDEBAR CONTROLS ----------
st.sidebar.title("List Controls")

if st.sidebar.button("🆕 Create New List"):
    st.session_state.df = pd.DataFrame(
        columns=[
            "Date Added",
            "Item Needed",
            "Quantity",
            "Where to Get",
            "Urgency",
            "Completed",
        ]
    )
    save_data(conn, st.session_state.df)
    st.sidebar.success("Started a new list!")

# Filters
st.sidebar.subheader("Filters")

urgency_filter = st.sidebar.multiselect(
    "Urgency",
    options=["Now", "Soon", "Yesterday!"],
    default=["Now", "Soon", "Yesterday!"],
)

show_completed = st.sidebar.checkbox("Show completed items", value=True)
search_text = st.sidebar.text_input("Search item or where to get")

# ---------- MAIN TITLE ----------
st.title("🛒 Modern Grocery List Manager")

st.caption(
    "Create, edit, and maintain your grocery list with persistent storage and Google Sheets."
)

# ---------- ADD ITEM FORM ----------
st.subheader("Add an item")

with st.form("add_item_form", clear_on_submit=True):
    c1, c2 = st.columns([2, 1])
    with c1:
        item_needed = st.text_input("Item Needed *", placeholder="e.g., Milk")
    with c2:
        quantity = st.text_input("Quantity (optional)", placeholder="e.g., 2 gallons")

    where_to_get = st.text_input(
        "Where to Get (optional)", placeholder="e.g., Walmart"
    )

    urgency = st.selectbox(
        "Urgency",
        ["Now", "Soon", "Yesterday!"],
        index=0,
    )

    submitted = st.form_submit_button("Add to List")

    if submitted:
        if not item_needed.strip():
            st.error("Item Needed is required.")
        else:
            new_row = {
                "Date Added": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Item Needed": item_needed.strip(),
                "Quantity": quantity.strip(),
                "Where to Get": where_to_get.strip(),
                "Urgency": urgency,
                "Completed": False,
            }
            st.session_state.df = pd.concat(
                [st.session_state.df, pd.DataFrame([new_row])],
                ignore_index=True,
            )
            save_data(conn, st.session_state.df)
            st.success(f"Added '{item_needed}' to the list!")

# ---------- FILTERED DATA ----------
df = st.session_state.df.copy()

if urgency_filter:
    df = df[df["Urgency"].isin(urgency_filter)]

if not show_completed:
    df = df[~df["Completed"]]

if search_text.strip():
    s = search_text.strip().lower()
    df = df[
        df["Item Needed"].str.lower().str.contains(s, na=False)
        | df["Where to Get"].str.lower().str.contains(s, na=False)
    ]

# ---------- EDITABLE TABLE ----------
st.subheader("Edit list")

if df.empty:
    st.info("Your list is empty or filter settings hide all items.")
else:
    # Use full DF (with all rows) for editing, but show filters on top
    # We'll present the filtered subset for editing.
    edited_df = st.data_editor(
        df,
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Urgency": st.column_config.SelectboxColumn(
                "Urgency",
                options=["Now", "Soon", "Yesterday!"],
            ),
            "Completed": st.column_config.CheckboxColumn("Completed"),
        },
    )

    # Merge edits back into the master DF using index alignment
    # (df is a filtered view of st.session_state.df)
    st.session_state.df.loc[edited_df.index, :] = edited_df
    save_data(conn, st.session_state.df)

# ---------- READ-ONLY STYLED VIEW ----------
st.subheader("Current list (styled view)")

if df.empty:
    st.info("No items to display.")
else:
    display_df = styled_urgency(df)

    # Make completed items visually dimmer
    completed_mask = display_df["Completed"]

    def style_row(row):
        if row["Completed"]:
            return ["color: #888; text-decoration: line-through" for _ in row]
        return [""] * len(row)

    st.dataframe(
        display_df.style.apply(style_row, axis=1),
        use_container_width=True,
    )

# ---------- EXPORT TO CSV ----------
st.subheader("Export")

if not st.session_state.df.empty:
    csv_buffer = StringIO()
    st.session_state.df.to_csv(csv_buffer, index=False)
    st.download_button(
        label="Download full list as CSV",
        data=csv_buffer.getvalue(),
        file_name="grocery_list.csv",
        mime="text/csv",
    )
else:
    st.caption("Nothing to export yet. Add some items first.")

