import streamlit as st
import pandas as pd
from database import create_tables, get_connection
import datetime


# ---------------- SETUP ----------------
create_tables()
st.set_page_config(page_title="PG Management System", layout="wide")

conn = get_connection()
cur = conn.cursor()

# ---------------- SESSION STATE ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None

# ---------------- LOGIN PAGE ----------------
if not st.session_state.logged_in:
    st.title("🏠 PG Management System")
    st.write(" ")
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.subheader("🔐 Login")
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")

        if st.button("Login"):
            cur.execute(
                "SELECT role FROM users WHERE username = ? AND password = ? AND status = 'ACTIVE'",
                (username_input, password_input)
            )
            user = cur.fetchone()

            if user:
                st.session_state.logged_in = True
                st.session_state.role = user[0].upper()
                st.session_state.username = username_input
                st.success(f"Logged in as {user[0].capitalize()}")
            else:
                st.error("Invalid credentials or inactive user.")
                st.stop()

# ---------------- DASHBOARD ----------------
role = st.session_state.role
username = st.session_state.username

if st.sidebar.button("🔓 Logout"):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None

if "tenant_added" not in st.session_state:
    st.session_state.tenant_added = False

# ---------------- ADMIN DASHBOARD ----------------
if role == "ADMIN":
    st.title("👑 Admin Dashboard")

    menu = st.sidebar.radio(
        "Admin Actions",
        ["Add Tenant", "View Tenants", "View Complaints", "View Rent Payment Records"]
    )

    # ---------------- ADD TENANT ----------------
    if menu == "Add Tenant":
        st.subheader("➕ Add Tenant")

        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            tenant_name = st.text_input("Tenant Name")
            contact = st.text_input("Phone Number")

            cur.execute(
                "SELECT room_id, room_no, sharing_type, capacity, current_occupancy, rent_per_person FROM rooms"
            )
            room_data = cur.fetchall()

            df_rooms = pd.DataFrame(
                room_data,
                columns=[
                    "room_id",
                    "room_no",
                    "sharing_type",
                    "capacity",
                    "current_occupancy",
                    "rent_per_person",
                ],
            )

            # Safe floor extraction
            df_rooms["floor"] = df_rooms["room_no"].astype(str).str[0]

            # Convert occupancy and capacity to int in case they are bytes
            df_rooms["capacity"] = df_rooms["capacity"].apply(lambda x: int.from_bytes(x, "little") if isinstance(x, bytes) else int(x))
            df_rooms["current_occupancy"] = df_rooms["current_occupancy"].apply(lambda x: int.from_bytes(x, "little") if isinstance(x, bytes) else int(x))

            floors = sorted(df_rooms["floor"].unique())
            selected_floor = st.selectbox("Select Floor", floors)

            available_rooms = df_rooms[
                (df_rooms["floor"] == selected_floor)
                & (df_rooms["current_occupancy"] < df_rooms["capacity"])
            ]

            # Keep only unique room numbers
            available_rooms = available_rooms.drop_duplicates(subset=["room_no"])

            if not available_rooms.empty:
                room_options = [
                    f"Room {row['room_no']} ({row['sharing_type'][0]})"
                    for _, row in available_rooms.iterrows()
                ]

                room_map = {
                    room_options[i]: available_rooms.iloc[i]
                    for i in range(len(room_options))
                }

                selected_room = st.selectbox("Select Room", room_options)
            else:
                st.warning("No available rooms on this floor")
                selected_room = None



            # 👇 space added before Add Tenant button
            if st.button("Add Tenant"):
                if not tenant_name or not contact or selected_room is None:
                    st.error("Please fill all fields and select a room")
                else:
                    room_info = room_map[selected_room]

                    room_id = int(room_info["room_id"])
                    rent_per_person = int(room_info["rent_per_person"])

                    cur.execute(
                        """
                        INSERT INTO tenants
                        (tenant_name, room_id, contact, deposit_amount, deposit_status)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (tenant_name, room_id, contact, rent_per_person, "HELD"),
                    )

                    cur.execute(
                        """
                        INSERT INTO users (username, password, role, status)
                        VALUES (?, ?, 'TENANT', 'ACTIVE')
                        """,
                        (tenant_name, contact),
                    )

                    cur.execute(
                        "UPDATE rooms SET current_occupancy = current_occupancy + 1 WHERE room_id = ?",
                        (room_id,),
                    )

                    conn.commit()

                    st.success(
                        f"Tenant {tenant_name} added successfully! Deposit: ₹{rent_per_person}"
                    )



    # ---------------- VIEW TENANTS ----------------
    elif menu == "View Tenants":
        st.subheader("📋 Tenant List")
        
        # Fetch tenants along with their room numbers
        cur.execute(
            "SELECT t.tenant_name, t.contact, r.room_no, t.deposit_amount, t.deposit_status "
            "FROM tenants t "
            "JOIN rooms r ON t.room_id = r.room_id"
        )
        tenants = cur.fetchall()

        if tenants:
            df_tenants = pd.DataFrame(tenants, columns=[
                "Tenant Name", "Contact", "Room No", "Deposit Amount", "Deposit Status"
            ])
            df_tenants["Room No"] = df_tenants["Room No"].astype(str)
            
            # Display all tenants without filtering
            st.table(df_tenants)
        else:
            st.info("No tenants in the system yet.")


    # ---------------- VIEW COMPLAINTS ----------------
    elif menu == "View Complaints":
        st.subheader("🛠 Complaints")
        cur.execute("""
            SELECT c.complaint_id, t.tenant_name, c.category, c.scope, c.description, c.status, c.created_at
            FROM complaints c
            JOIN tenants t ON c.tenant_id = t.tenant_id
        """)
        complaints = cur.fetchall()

        if complaints:
            df_complaints = pd.DataFrame(complaints, columns=[
                "Complaint ID", "Tenant Name", "Category", "Scope", "Description", "Status", "Created At"
            ])
            st.table(df_complaints)

            st.subheader("Update Complaint Status")
            complaint_ids = df_complaints["Complaint ID"].tolist()
            selected_complaint = st.selectbox("Select Complaint ID", complaint_ids)
            new_status = st.selectbox("Set New Status", ["OPEN", "RESOLVED", "IN PROGRESS", "CLOSED"])

            if st.button("Update Status"):
                cur.execute(
                    "UPDATE complaints SET status = ? WHERE complaint_id = ?",
                    (new_status, selected_complaint)
                )
                conn.commit()
                st.success(f"Complaint ID {selected_complaint} status updated to {new_status}")
        else:
            st.info("No complaints found.")

    # ---------------- VIEW RENT PAYMENTS ----------------
    elif menu == "View Rent Payment Records":
        st.subheader("💰 Rent Payment Records")

        # Fetch all tenants
        cur.execute("SELECT tenant_id, tenant_name FROM tenants")
        all_tenants = cur.fetchall()
        tenant_dict = {t[0]: t[1] for t in all_tenants}

        # Get tenants who have PAID (any time)
        cur.execute("SELECT tenant_id FROM rent_payments WHERE status = 'PAID'")
        paid_tenants = [row[0] for row in cur.fetchall()]

        # Tenants who have not paid
        unpaid_tenants = [(tid, tenant_dict[tid]) for tid in tenant_dict if tid not in paid_tenants]

        if unpaid_tenants:
            df_unpaid = pd.DataFrame(unpaid_tenants, columns=["Tenant ID", "Tenant Name"])
            st.subheader("Tenants with Pending Rent")
            st.table(df_unpaid)
        else:
            st.success("All tenants have paid their rent.")

        # ---------------- Tenants who paid rent this month ----------------
        current_month = datetime.datetime.now().strftime("%Y-%m")
        cur.execute(
            "SELECT t.tenant_id, t.tenant_name FROM rent_payments rp "
            "JOIN tenants t ON rp.tenant_id = t.tenant_id "
            "WHERE rp.status='PAID' AND rp.month=?",
            (current_month,)
        )
        paid_this_month = cur.fetchall()

        if paid_this_month:
            df_paid_month = pd.DataFrame(paid_this_month, columns=["Tenant ID", "Tenant Name"])
            st.subheader(f"Tenants who paid rent for {current_month}")
            st.table(df_paid_month)
        else:
            st.info(f"No tenants have paid rent for {current_month} yet.")


# ---------------- TENANT DASHBOARD ----------------
elif role == "TENANT":
    st.title(f"👤 Tenant Dashboard - {username}")
    menu = st.sidebar.radio("Tenant Actions", ["My Rent", "Raise Complaint"])

    if menu == "My Rent":
        st.subheader("💰 Rent Details")

        # Get tenant details
        cur.execute(
            "SELECT tenant_id, room_id, deposit_amount FROM tenants WHERE tenant_name=?",
            (username,)
        )
        tenant = cur.fetchone()

        if tenant:
            tenant_id, room_id, deposit_amount = tenant

            # Get current month in format 'YYYY-MM'
            current_month = datetime.datetime.now().strftime("%Y-%m")

            # Check if rent already paid for current month
            cur.execute(
                "SELECT * FROM rent_payments WHERE tenant_id=? AND month=?",
                (tenant_id, current_month)
            )
            payment = cur.fetchone()

            if payment:
                st.success(f"✅ Rent for {current_month} is already paid!")
            else:
                st.warning(f"⚠️ Rent for {current_month} is due!")

                if st.button("Pay Rent Now"):
                    # Assume rent_amount = deposit_amount for simplicity
                    rent_amount = deposit_amount
                    paid_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cur.execute(
                        """
                        INSERT INTO rent_payments (
                            tenant_id, month, rent_amount, total_amount, status, due_date, paid_date
                        )
                        VALUES (?, ?, ?, ?, 'PAID', ?, ?)
                        """,
                        (tenant_id, current_month, rent_amount, rent_amount, paid_date, paid_date)
                    )
                    conn.commit()
                    st.success(f"✅ Rent for {current_month} paid successfully!")
        else:
            st.warning("Tenant record not found!")

    elif menu == "Raise Complaint":
        complaint_text = st.text_area("Describe your complaint")

        if st.button("Submit Complaint"):
            # Insert complaint into the complaints table
            cur.execute(
                """
                INSERT INTO complaints (tenant_id, description, status, created_at)
                VALUES (
                    (SELECT tenant_id FROM tenants WHERE tenant_name=?),
                    ?, 
                    'OPEN',
                    CURRENT_TIMESTAMP
                )
                """,
                (username, complaint_text)
            )
            conn.commit()
            st.success("Complaint submitted!")



# ---------------- CLOSE CONNECTION ----------------
conn.close()
