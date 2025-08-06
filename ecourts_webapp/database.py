import sqlite3
import json, os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional

class CaseDatabase:
    def __init__(self, db_path="data/cases.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Cases table with new columns
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cino TEXT UNIQUE,
                case_no TEXT,
                petparty_name TEXT,
                resparty_name TEXT,
                establishment_name TEXT,
                state_name TEXT,
                district_name TEXT,
                date_next_list TEXT,
                date_last_list TEXT,
                purpose_name TEXT,
                type_name TEXT,
                court_no_desg_name TEXT,
                disp_name TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_notes TEXT DEFAULT '',
                is_changed BOOLEAN DEFAULT FALSE,
                change_summary TEXT DEFAULT '',
                raw_data TEXT,
                user_side TEXT DEFAULT '',
                reg_no INTEGER,
                reg_year INTEGER
            )
        """)

        # Add new columns if they don't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE cases ADD COLUMN user_side TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("ALTER TABLE cases ADD COLUMN reg_no INTEGER")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE cases ADD COLUMN reg_year INTEGER")
        except sqlite3.OperationalError:
            pass

        # Change history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS case_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cino TEXT,
                field_name TEXT,
                old_value TEXT,
                new_value TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cino) REFERENCES cases (cino)
            )
        """)

        conn.commit()
        conn.close()

    def process_daily_file(self, file_path: str) -> Dict[str, int]:
        """Process daily myCases.txt file and detect changes"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_content = f.read().strip()

            if not raw_content:
                return {"error": "File is empty"}

            # Try to parse the file in different formats
            data_list = []
            try:
                # Format 1: List of JSON strings ["{ ... }", "{ ... }"]
                parsed = json.loads(raw_content)
                if isinstance(parsed, list):
                    # Check if it's a list of strings (JSON format)
                    if all(isinstance(item, str) for item in parsed):
                        data_list = [json.loads(item) for item in parsed]
                    # Or a list of objects directly
                    elif all(isinstance(item, dict) for item in parsed):
                        data_list = parsed
                    else:
                        raise ValueError("Invalid list format")
                elif isinstance(parsed, dict):
                    # Format 3: Single JSON object
                    data_list = [parsed]
                else:
                    raise ValueError("Invalid JSON format")

            except (json.JSONDecodeError, ValueError):
                try:
                    # Format 2: One JSON object per line
                    lines = raw_content.splitlines()
                    data_list = []
                    for line in lines:
                        line = line.strip()
                        if line:  # Skip empty lines
                            data_list.append(json.loads(line))
                except json.JSONDecodeError as e:
                    return {"error": f"Invalid JSON format: {str(e)}"}

            if not data_list:
                return {"error": "No valid case data found in file"}

            # Process the data
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            stats = {"new": 0, "updated": 0, "unchanged": 0}

            for case_data in data_list:
                if not isinstance(case_data, dict):
                    continue

                cino = case_data.get('cino')
                if not cino:
                    continue

                # Extract reg_no and reg_year from the case data
                reg_no = case_data.get('reg_no')
                reg_year = case_data.get('reg_year')

                # Check if case exists
                cursor.execute("SELECT * FROM cases WHERE cino = ?", (cino,))
                existing_case = cursor.fetchone()

                if existing_case:
                    # Check for changes
                    changes = self._detect_changes(existing_case, case_data)
                    if changes:
                        self._update_case_with_changes(cursor, cino, case_data, changes)
                        stats["updated"] += 1
                    else:
                        stats["unchanged"] += 1
                else:
                    # New case
                    self._insert_new_case(cursor, case_data)
                    stats["new"] += 1

            conn.commit()
            conn.close()

            print("📊 Daily file processed:", stats)
            return stats

        except Exception as e:
            print(f"Error processing file: {e}")
            import traceback
            traceback.print_exc()
            return {"error": f"Processing failed: {str(e)}"}

    def _detect_changes(self, existing_case: tuple, new_data: dict) -> List[Dict]:
        """Detect changes between existing case and new data"""
        changes = []
        field_mapping = {
            2: 'case_no', 3: 'petparty_name', 4: 'resparty_name',
            5: 'establishment_name', 6: 'state_name', 7: 'district_name',
            8: 'date_next_list', 9: 'date_last_list', 10: 'purpose_name',
            11: 'type_name', 12: 'court_no_desg_name', 13: 'disp_name'
        }

        for idx, field_name in field_mapping.items():
            # Handle None values properly
            old_value = existing_case[idx] if existing_case[idx] is not None else ""
            new_value = str(new_data.get(field_name, "") or "") # Handle None from new_data too

            if old_value != new_value:
                changes.append({
                    'field': field_name,
                    'old_value': old_value,
                    'new_value': new_value
                })

        return changes

    def _update_case_with_changes(self, cursor, cino: str, case_data: dict, changes: List[Dict]):
        """Update case and record changes"""
        # Update main case record with proper None handling
        cursor.execute("""
            UPDATE cases SET
                case_no=?, petparty_name=?, resparty_name=?, establishment_name=?,
                state_name=?, district_name=?, date_next_list=?, date_last_list=?,
                purpose_name=?, type_name=?, court_no_desg_name=?, disp_name=?,
                is_changed=TRUE, change_summary=?, raw_data=?, updated_at=CURRENT_TIMESTAMP,
                reg_no=?, reg_year=?
            WHERE cino=?
        """, (
            case_data.get('case_no') or '',
            case_data.get('petparty_name') or '',
            case_data.get('resparty_name') or '',
            case_data.get('establishment_name') or '',
            case_data.get('state_name') or '',
            case_data.get('district_name') or '',
            case_data.get('date_next_list') or '',
            case_data.get('date_last_list') or '',
            case_data.get('purpose_name') or '',
            case_data.get('type_name') or '',
            case_data.get('court_no_desg_name') or '',
            case_data.get('disp_name') or '',
            json.dumps([f"{c['field']}: {c['old_value']} → {c['new_value']}" for c in changes]),
            json.dumps(case_data),
            case_data.get('reg_no'),
            case_data.get('reg_year'),
            cino
        ))

        # Record individual changes
        for change in changes:
            cursor.execute("""
                INSERT INTO case_history (cino, field_name, old_value, new_value)
                VALUES (?, ?, ?, ?)
            """, (cino, change['field'], change['old_value'], change['new_value']))

    def _insert_new_case(self, cursor, case_data: dict):
        """Insert new case record"""
        cursor.execute("""
            INSERT INTO cases (
                cino, case_no, petparty_name, resparty_name, establishment_name,
                state_name, district_name, date_next_list, date_last_list,
                purpose_name, type_name, court_no_desg_name, disp_name, raw_data,
                reg_no, reg_year
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            case_data.get('cino') or '',
            case_data.get('case_no') or '',
            case_data.get('petparty_name') or '',
            case_data.get('resparty_name') or '',
            case_data.get('establishment_name') or '',
            case_data.get('state_name') or '',
            case_data.get('district_name') or '',
            case_data.get('date_next_list') or '',
            case_data.get('date_last_list') or '',
            case_data.get('purpose_name') or '',
            case_data.get('type_name') or '',
            case_data.get('court_no_desg_name') or '',
            case_data.get('disp_name') or '',
            json.dumps(case_data),
            case_data.get('reg_no'),
            case_data.get('reg_year')
        ))

    def create_new_case(self, case_data: dict) -> bool:
        """Create a new case manually"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if CINO already exists
            cursor.execute("SELECT cino FROM cases WHERE cino = ?", (case_data.get('cino'),))
            if cursor.fetchone():
                conn.close()
                return False, "Case with this CINO already exists"

            self._insert_new_case(cursor, case_data)
            conn.commit()
            conn.close()
            return True, "Case created successfully"

        except Exception as e:
            print(f"Error creating case: {e}")
            return False, str(e)

    def get_all_cases(self) -> List[Dict]:
        """Get all cases with change status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM cases ORDER BY
            CASE WHEN is_changed = 1 THEN 0 ELSE 1 END,
            updated_at DESC
        """)

        cases = cursor.fetchall()
        conn.close()

        return [self._row_to_dict(case) for case in cases]

    def get_case_by_cino(self, cino: str) -> Optional[Dict]:
        """Get specific case by CINO"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cases WHERE cino = ?", (cino,))
        case = cursor.fetchone()
        conn.close()
        return self._row_to_dict(case) if case else None

    def update_case_notes(self, cino: str, notes: str, other_updates: dict = None) -> bool:
        """Update case notes and other fields"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if other_updates:
            # Build dynamic update query
            update_fields = ["user_notes = ?"]
            values = [notes]

            for field, value in other_updates.items():
                update_fields.append(f"{field} = ?")
                values.append(value)

            values.append(cino)
            cursor.execute(f"""
                UPDATE cases SET {', '.join(update_fields)}
                WHERE cino = ?
            """, values)
        else:
            cursor.execute("UPDATE cases SET user_notes = ? WHERE cino = ?", (notes, cino))

        conn.commit()
        conn.close()
        return True

    def mark_case_reviewed(self, cino: str):
        """Mark case as reviewed (clear change flag)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE cases SET is_changed = FALSE WHERE cino = ?", (cino,))
        conn.commit()
        conn.close()

    def _row_to_dict(self, row: tuple) -> Dict:
        """Convert database row to dictionary"""
        if not row:
            return None

        columns = [
            'id', 'cino', 'case_no', 'petparty_name', 'resparty_name',
            'establishment_name', 'state_name', 'district_name', 'date_next_list',
            'date_last_list', 'purpose_name', 'type_name', 'court_no_desg_name',
            'disp_name', 'updated_at', 'user_notes', 'is_changed', 'change_summary', 
            'raw_data', 'user_side', 'reg_no', 'reg_year'
        ]

        result = dict(zip(columns, row))
        result['is_changed'] = bool(result['is_changed'])
        return result

    def get_reviewed_cases_with_notes(self) -> List[Dict]:
        """Get cases that have been reviewed and have user notes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM cases
            WHERE is_changed = FALSE
              AND user_notes IS NOT NULL
              AND user_notes != ''
            ORDER BY updated_at DESC
        """)

        cases = cursor.fetchall()
        conn.close()

        return [self._row_to_dict(case) for case in cases]

    def clear_all_data(self) -> Dict[str, int]:
        """
        Clear all case data from the database.
        Returns:
            Dictionary with deletion statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get counts before deletion
            cursor.execute("SELECT COUNT(*) FROM cases")
            cases_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM case_history")
            history_count = cursor.fetchone()[0]

            # Delete all data
            cursor.execute("DELETE FROM case_history")
            cursor.execute("DELETE FROM cases")

            # Reset auto-increment counters
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='cases'")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='case_history'")

            conn.commit()
            conn.close()

            print(f"🗑️ Database cleared: {cases_count} cases, {history_count} history records")
            return {
                'cases_deleted': cases_count,
                'history_deleted': history_count,
                'total_deleted': cases_count + history_count
            }

        except Exception as e:
            print(f"Error clearing database: {e}")
            return {
                'cases_deleted': 0,
                'history_deleted': 0,
                'total_deleted': 0,
                'error': str(e)
            }

    def backup_data_before_clear(self, backup_path: str = None) -> str:
        """
        Create a backup of all data before clearing.
        Args:
            backup_path: Optional custom backup path
        Returns:
            Path to the backup file
        """
        try:
            import shutil
            from datetime import datetime

            if not backup_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = f"data/backup_cases_{timestamp}.db"

            # Create backup directory if it doesn't exist
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)

            # Copy the database file
            shutil.copy2(self.db_path, backup_path)
            print(f"💾 Database backup created: {backup_path}")
            return backup_path

        except Exception as e: 
            print(f"Error creating backup: {e}")
            return None
        
    def get_upcoming_hearings(self) -> List[Dict]:
        """Get cases with upcoming hearing dates"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get cases with valid future dates
        cursor.execute("""
            SELECT * FROM cases 
            WHERE date_next_list IS NOT NULL 
            AND date_next_list != '' 
            AND date_next_list != 'Not scheduled'
            AND date(date_next_list) >= date('now')
            ORDER BY date_next_list ASC
        """)
        
        cases = cursor.fetchall()
        conn.close()
        return [self._row_to_dict(case) for case in cases]

    def get_petitioner_cases(self) -> List[Dict]:
        """Get cases where user is petitioner"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM cases WHERE user_side = 'petitioner' ORDER BY updated_at DESC")
        cases = cursor.fetchall()
        conn.close()
        return [self._row_to_dict(case) for case in cases]

    def get_respondent_cases(self) -> List[Dict]:
        """Get cases where user is respondent"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM cases WHERE user_side = 'respondent' ORDER BY updated_at DESC")
        cases = cursor.fetchall()
        conn.close()
        return [self._row_to_dict(case) for case in cases]

    def get_case_counts(self) -> Dict[str, int]:
        """Get counts for different case categories"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total cases
        cursor.execute("SELECT COUNT(*) FROM cases")
        total_cases = cursor.fetchone()[0]
        
        # Changed cases
        cursor.execute("SELECT COUNT(*) FROM cases WHERE is_changed = TRUE")
        changed_cases = cursor.fetchone()[0]
        
        # Reviewed cases
        cursor.execute("SELECT COUNT(*) FROM cases WHERE is_changed = FALSE AND user_notes IS NOT NULL AND user_notes != ''")
        reviewed_cases = cursor.fetchone()[0]
        
        # Petitioner cases
        cursor.execute("SELECT COUNT(*) FROM cases WHERE user_side = 'petitioner'")
        petitioner_cases = cursor.fetchone()[0]
        
        # Respondent cases
        cursor.execute("SELECT COUNT(*) FROM cases WHERE user_side = 'respondent'")
        respondent_cases = cursor.fetchone()[0]
        
        # Upcoming hearings
        cursor.execute("""
            SELECT COUNT(*) FROM cases 
            WHERE date_next_list IS NOT NULL 
            AND date_next_list != '' 
            AND date_next_list != 'Not scheduled'
            AND date(date_next_list) >= date('now')
        """)
        upcoming_hearings = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_cases': total_cases,
            'changed_cases': changed_cases,
            'reviewed_cases': reviewed_cases,
            'petitioner_cases': petitioner_cases,
            'respondent_cases': respondent_cases,
            'upcoming_hearings': upcoming_hearings
        }
