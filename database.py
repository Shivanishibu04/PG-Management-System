import sqlite3

def get_connection():
    return sqlite3.connect("pg_management.db", check_same_thread=False)

def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    # ---------------- ROOMS TABLE ----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        room_id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_no TEXT,
        sharing_type TEXT,
        capacity INTEGER,
        current_occupancy INTEGER DEFAULT 0,
        rent_per_person INTEGER
    )
    """)

    # ---------------- TENANTS TABLE ----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tenants (
        tenant_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        tenant_name TEXT,
        contact TEXT,
        room_id INTEGER,
        deposit_amount INTEGER,
        deposit_status TEXT CHECK (deposit_status IN ('HELD', 'REFUNDED', 'PARTIAL')),
        FOREIGN KEY (room_id) REFERENCES rooms(room_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)

    # ---------------- COMPLAINTS TABLE ----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        complaint_id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER,
        category TEXT,
        scope TEXT,
        description TEXT,
        status TEXT DEFAULT 'OPEN',
        created_at TEXT,
        FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
    )
    """)

    # ---------------- RENT PAYMENTS TABLE ----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rent_payments (
        rent_id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER,
        month TEXT,
        rent_amount INTEGER,
        late_fee INTEGER DEFAULT 0,
        total_amount INTEGER,
        status TEXT CHECK (status IN ('PAID', 'PENDING', 'LATE')),
        due_date TEXT,
        paid_date TEXT,
        FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
    )
    """)

    # ---------------- USERS TABLE ----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT CHECK(role IN ('ADMIN', 'TENANT')) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT CHECK(status IN ('ACTIVE', 'INACTIVE')) DEFAULT 'ACTIVE'
    )
    """)

    # Insert default admin
    cur.execute("""
    INSERT OR IGNORE INTO users(username, password, role) VALUES ('Admin user', '123', 'ADMIN')
    """)

    # ---------------- INSERT 15 ROOMS (mixed per floor) ----------------
    floors = 5
    for floor in range(1, floors + 1):
        # Single room
        cur.execute("""
        INSERT OR IGNORE INTO rooms (room_no, sharing_type, capacity, current_occupancy, rent_per_person)
        VALUES (?, ?, ?, ?, ?)
        """, (f"{floor}S", "Single", 1, 0, 5000))
        
        # Double room
        cur.execute("""
        INSERT OR IGNORE INTO rooms (room_no, sharing_type, capacity, current_occupancy, rent_per_person)
        VALUES (?, ?, ?, ?, ?)
        """, (f"{floor}D", "Double", 2, 0, 3000))
        
        # Four-sharing room
        cur.execute("""
        INSERT OR IGNORE INTO rooms (room_no, sharing_type, capacity, current_occupancy, rent_per_person)
        VALUES (?, ?, ?, ?, ?)
        """, (f"{floor}F", "Four Sharing", 4, 0, 2000))

    conn.commit()
    conn.close()
