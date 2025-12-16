import streamlit as st
import pandas as pd
from database import create_tables, get_connection

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
                st.stop()  # Stop only if login fails

# ---------------- DASHBOARD ----------------
role = st.session_state.role
username = st.session_state.username

# ---------------- ADMIN DASHBOARD ----------------
if role == "ADMIN":
    st.title("👑 Admin Dashboard")

    # ----------- Admin Navigation Bar in Sidebar -----------
    menu = st.sidebar.radio(
        "Admin Actions",
        ["Add Tenant", "View Tenants", "View Complaints", "View Rent Payment Records"]
    )

    if menu == "Add Tenant":
        st.subheader("➕ Add Tenant")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            tenant_name = st.text_input("Tenant Name")
            contact = st.text_input("Phone Number")

            # Fetch all rooms
            cur.execute(
                "SELECT room_id, room_no, sharing_type, capacity, current_occupancy, rent_per_person FROM rooms"
            )
            room_data = cur.fetchall()
            df_rooms = pd.DataFrame(room_data, columns=[
                "room_id", "room_no", "sharing_type", "capacity", "current_occupancy", "rent_per_person"
            ])

            # Add floor column (assuming first digit of room_no is floor)
            df_rooms["floor"] = df_rooms["room_no"].str[0]

            # Select floor first
            floors = sorted(df_rooms["floor"].unique())
            selected_floor = st.selectbox("Select Floor", floors)

            # Filter rooms for selected floor and available spots
            available_rooms = df_rooms[
                (df_rooms["floor"] == selected_floor) & 
                (df_rooms["capacity"] > df_rooms["current_occupancy"])
            ]

            if not available_rooms.empty:
                # Only show Room No and Sharing Type
                room_options = [
                    f"Room {row['room_no']} ({row['sharing_type'][0]})"
                    for _, row in available_rooms.iterrows()
                ]
                room_map = {room_options[i]: available_rooms.iloc[i] for i in range(len(room_options))}
                selected_room = st.selectbox("Select Room", room_options)
            else:
                st.warning("No available rooms on this floor")
                selected_room = None

            if st.button("Add Tenant"):
                if not tenant_name or not contact or selected_room is None:
                    st.error("Please fill all fields and select a room")
                else:
                    room_info = room_map[selected_room]
                    room_id, rent_per_person = room_info["room_id"], room_info["rent_per_person"]

                    # Insert tenant
                    cur.execute(
                        "INSERT INTO tenants (tenant_name, room_id, contact, deposit_amount, deposit_status) VALUES (?, ?, ?, ?, ?)",
                        (tenant_name, room_id, contact, rent_per_person, "HELD")
                    )

                    # Update room occupancy
                    cur.execute(
                        "UPDATE rooms SET current_occupancy = current_occupancy + 1 WHERE room_id = ?",
                        (room_id,)
                    )
                    conn.commit()
                    st.success(f"Tenant {tenant_name} added successfully! Deposit: ₹{rent_per_person}")

    elif menu == "View Tenants":
        st.subheader("📋 Tenant List")

        # Fetch tenants with room info
        cur.execute(
            "SELECT t.tenant_name, t.contact, r.room_no, t.deposit_amount, t.deposit_status "
            "FROM tenants t JOIN rooms r ON t.room_id = r.room_id"
        )
        tenants = cur.fetchall()
        df_tenants = pd.DataFrame(tenants, columns=[
            "Tenant Name", "Contact", "Room No", "Deposit Amount", "Deposit Status"
        ])

        if not df_tenants.empty:
            # Extract floor from room_no: assume first character is floor if numeric
            def get_floor(room_no):
                for ch in room_no:
                    if ch.isdigit():
                        return ch
                return "Unknown"

            df_tenants["Floor"] = df_tenants["Room No"].apply(get_floor)

            # Select floor
            floors = sorted(df_tenants["Floor"].unique())
            selected_floor = st.selectbox("Select Floor to view tenants", floors)

            # Filter tenants by selected floor
            tenants_on_floor = df_tenants[df_tenants["Floor"] == selected_floor]

            if not tenants_on_floor.empty:
                st.table(tenants_on_floor.drop(columns=["Floor"]))  # Optional: hide floor column
            else:
                st.info("No tenants found on this floor.")
        else:
            st.info("No tenants in the system yet.")



    elif menu == "View Complaints":
        st.subheader("🛠 Complaints")
        # Fetch all complaints with tenant info
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

            # Option to update complaint status
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


    elif menu == "View Rent Payment Records":
        st.subheader("💰 Rent Payment Records")

        # Fetch all tenants
        cur.execute("SELECT tenant_id, tenant_name FROM tenants")
        all_tenants = cur.fetchall()
        tenant_dict = {t[0]: t[1] for t in all_tenants}

        # Fetch tenants who have paid rent
        cur.execute("SELECT tenant_id FROM rent_payments WHERE status = 'PAID'")
        paid_tenants = [row[0] for row in cur.fetchall()]

        # Compute tenants who have not paid
        unpaid_tenants = [(tid, tenant_dict[tid]) for tid in tenant_dict if tid not in paid_tenants]

        if unpaid_tenants:
            df_unpaid = pd.DataFrame(unpaid_tenants, columns=["Tenant ID", "Tenant Name"])
            st.table(df_unpaid)
        else:
            st.success("All tenants have paid their rent.")


# ---------------- TENANT DASHBOARD ----------------
elif role == "TENANT":
    st.title(f"👤 Tenant Dashboard - {username}")

    menu = st.sidebar.radio("Tenant Actions", ["My Rent", "Raise Complaint"])

    if menu == "My Rent":
        if st.button("View Rent Details"):
            cur.execute(
                "SELECT r.room_no, t.deposit_amount "
                "FROM tenants t JOIN rooms r ON t.room_id = r.room_id "
                "WHERE t.tenant_name = ?",
                (username,)
            )
            data = cur.fetchone()
            if data:
                st.info(f"Room No: {data[0]}")
                st.success(f"Deposit Paid: ₹{data[1]}")
            else:
                st.warning("Tenant record not found!")

    elif menu == "Raise Complaint":
        complaint_text = st.text_area("Describe your complaint")
        if st.button("Submit Complaint"):
            cur.execute(
                "INSERT INTO complaints (tenant_id, description, status) VALUES "
                "((SELECT tenant_id FROM tenants WHERE tenant_name=?), ?, 'OPEN')",
                (username, complaint_text)
            )
            conn.commit()
            st.success("Complaint submitted!")

# ---------------- CLOSE CONNECTION ----------------
conn.close()
