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

        # Cases table with new columns - FIXED: DEFAULT FALSE for is_changed
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
            reg_year INTEGER,
            date_of_decision TEXT DEFAULT NULL
        )
        """)

        # Add new columns if they don't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE cases ADD COLUMN user_side TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass # Column already exists

        try:
            cursor.execute("ALTER TABLE cases ADD COLUMN reg_no INTEGER")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE cases ADD COLUMN reg_year INTEGER")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("ALTER TABLE cases ADD COLUMN date_of_decision TEXT DEFAULT NULL")
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
        """Process daily myCases.txt file and detect changes - FIXED"""
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
                        if line: # Skip empty lines
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

                # Check if case exists
                cursor.execute("SELECT * FROM cases WHERE cino = ?", (cino,))
                existing_case = cursor.fetchone()
                
                if existing_case:
                    # Check for changes
                    changes = self._detect_changes(existing_case, case_data)
                    if changes:
                        # ONLY cases with actual changes are marked for review
                        self._update_case_with_changes(cursor, cino, case_data, changes)
                        stats["updated"] += 1
                    else:
                        stats["unchanged"] += 1
                else:
                    # FIXED: New case - insert as NOT CHANGED (is_changed=FALSE)
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
        """Update case and record changes - FIXED: Use consistent data extraction"""
        
        # Use the same field extraction logic
        def get_field_value(field_name, case_data):
            outer_value = case_data.get(field_name, '')
            if not outer_value and 'raw_data' in case_data:
                try:
                    raw_data_str = case_data.get('raw_data', '{}')
                    if isinstance(raw_data_str, str):
                        raw_data = json.loads(raw_data_str)
                        inner_value = raw_data.get(field_name, '')
                        return inner_value if inner_value else outer_value
                except (json.JSONDecodeError, TypeError):
                    pass
            return outer_value if outer_value else ''
        
        cursor.execute("""
            UPDATE cases SET
            case_no=?, petparty_name=?, resparty_name=?, establishment_name=?,
            state_name=?, district_name=?, date_next_list=?, date_last_list=?,
            purpose_name=?, type_name=?, court_no_desg_name=?, disp_name=?,
            is_changed=TRUE, change_summary=?, raw_data=?, updated_at=CURRENT_TIMESTAMP,
            reg_no=?, reg_year=?, user_notes=?, user_side=?
            WHERE cino=?
        """, (
            get_field_value('case_no', case_data),
            get_field_value('petparty_name', case_data),
            get_field_value('resparty_name', case_data),
            get_field_value('establishment_name', case_data),
            get_field_value('state_name', case_data),
            get_field_value('district_name', case_data),
            get_field_value('date_next_list', case_data),
            get_field_value('date_last_list', case_data),
            get_field_value('purpose_name', case_data),
            get_field_value('type_name', case_data),
            get_field_value('court_no_desg_name', case_data),
            get_field_value('disp_name', case_data),
            json.dumps([f"{c['field']}: {c['old_value']} → {c['new_value']}" for c in changes]),
            json.dumps(case_data),
            case_data.get('reg_no'),
            case_data.get('reg_year'),
            get_field_value('user_notes', case_data),  # FIXED
            get_field_value('user_side', case_data),   # FIXED
            cino
        ))

        # Record individual changes
        for change in changes:
            cursor.execute("""
            INSERT INTO case_history (cino, field_name, old_value, new_value)
            VALUES (?, ?, ?, ?)
            """, (cino, change['field'], change['old_value'], change['new_value']))

    
    def _insert_new_case(self, cursor, case_data: dict):
        """Insert new case record - FIXED: Handle nested JSON properly for ALL fields"""
        
        cino = case_data.get('cino', '').strip()
        print(f"🔍 Processing case: {cino}")
        
        # FIXED: Extract data with proper priority handling
        def get_field_value(field_name, case_data):
            """Get field value with fallback logic"""
            # Priority 1: Direct field from outer JSON
            outer_value = case_data.get(field_name, '')
            
            # Priority 2: If empty, try from raw_data (parsed)
            if not outer_value and 'raw_data' in case_data:
                try:
                    raw_data_str = case_data.get('raw_data', '{}')
                    if isinstance(raw_data_str, str):
                        raw_data = json.loads(raw_data_str)
                        inner_value = raw_data.get(field_name, '')
                        return inner_value if inner_value else outer_value
                except (json.JSONDecodeError, TypeError):
                    pass
            
            return outer_value if outer_value else ''
        
        # FIXED: Extract all fields using consistent logic
        extracted_data = {
            'cino': get_field_value('cino', case_data),
            'case_no': get_field_value('case_no', case_data),
            'petparty_name': get_field_value('petparty_name', case_data),
            'resparty_name': get_field_value('resparty_name', case_data),
            'establishment_name': get_field_value('establishment_name', case_data),
            'state_name': get_field_value('state_name', case_data),
            'district_name': get_field_value('district_name', case_data),
            'date_next_list': get_field_value('date_next_list', case_data),
            'date_last_list': get_field_value('date_last_list', case_data),
            'purpose_name': get_field_value('purpose_name', case_data),
            'type_name': get_field_value('type_name', case_data),
            'court_no_desg_name': get_field_value('court_no_desg_name', case_data),
            'disp_name': get_field_value('disp_name', case_data),
            'user_notes': get_field_value('user_notes', case_data),
            'user_side': get_field_value('user_side', case_data),
            'reg_no': case_data.get('reg_no') or None,
            'reg_year': case_data.get('reg_year') or None,
            'date_of_decision': get_field_value('date_of_decision', case_data)
        }
        
        # Debug logging
        print(f"📝 Extracted data for {cino}:")
        print(f"   user_notes: '{extracted_data['user_notes']}'")
        print(f"   petparty_name: '{extracted_data['petparty_name'][:50]}...'")
        print(f"   case_no: '{extracted_data['case_no']}'")
        
        cursor.execute("""
            INSERT INTO cases (
                cino, case_no, petparty_name, resparty_name, establishment_name,
                state_name, district_name, date_next_list, date_last_list,
                purpose_name, type_name, court_no_desg_name, disp_name, raw_data,
                reg_no, reg_year, is_changed, date_of_decision, user_notes, user_side
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            extracted_data['cino'],
            extracted_data['case_no'],
            extracted_data['petparty_name'],
            extracted_data['resparty_name'],
            extracted_data['establishment_name'],
            extracted_data['state_name'],
            extracted_data['district_name'],
            extracted_data['date_next_list'],
            extracted_data['date_last_list'],
            extracted_data['purpose_name'],
            extracted_data['type_name'],
            extracted_data['court_no_desg_name'],
            extracted_data['disp_name'],
            json.dumps(case_data),  # Store original for reference
            extracted_data['reg_no'],
            extracted_data['reg_year'],
            False,  # is_changed
            extracted_data['date_of_decision'],
            extracted_data['user_notes'],  # FIXED: Use extracted notes
            extracted_data['user_side']    # FIXED: Use extracted user_side
        ))
        
        print(f"✅ Case {cino} inserted with correct data")

    def create_new_case(self, case_data: dict) -> tuple[bool, str]:
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

    def mark_case_as_reviewed(self, cino: str) -> bool:
        """Mark single case as reviewed without requiring notes"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
            UPDATE cases
            SET is_changed = FALSE,
                updated_at = CURRENT_TIMESTAMP
            WHERE cino = ?
            """, (cino,))
            
            # Record in history
            cursor.execute("""
            INSERT INTO case_history (cino, field_name, old_value, new_value)
            VALUES (?, 'marked_reviewed', 'pending', 'reviewed')
            """, (cino,))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            
            if success:
                print(f"✅ Marked case {cino} as reviewed")
            return success
            
        except Exception as e:
            print(f"Error marking case as reviewed: {e}")
            return False

    def get_reviewed_cases_with_notes(self) -> List[Dict]:
        """Get cases that have been reviewed (is_changed = FALSE)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        SELECT * FROM cases
        WHERE is_changed = FALSE
        ORDER BY updated_at DESC
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

    def get_unassigned_cases(self) -> List[Dict]:
        """Get cases where user_side is not set"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cases WHERE user_side IS NULL OR user_side = '' ORDER BY updated_at DESC")
        cases = cursor.fetchall()
        conn.close()
        return [self._row_to_dict(case) for case in cases]

    def get_case_counts(self) -> Dict[str, int]:
        """Get counts for law firm dashboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total cases
        cursor.execute("SELECT COUNT(*) FROM cases")
        total_cases = cursor.fetchone()[0]
        
        # Changed cases (pending review) 
        cursor.execute("SELECT COUNT(*) FROM cases WHERE is_changed = TRUE")
        changed_cases = cursor.fetchone()[0]
        
        # Reviewed cases (is_changed = FALSE only)
        cursor.execute("SELECT COUNT(*) FROM cases WHERE is_changed = FALSE")
        reviewed_cases = cursor.fetchone()[0]
        
        # Petitioner cases
        cursor.execute("SELECT COUNT(*) FROM cases WHERE user_side = 'petitioner'")
        petitioner_cases = cursor.fetchone()[0]
        
        # Respondent cases
        cursor.execute("SELECT COUNT(*) FROM cases WHERE user_side = 'respondent'")
        respondent_cases = cursor.fetchone()[0]
        
        # Cases without user side set
        cursor.execute("SELECT COUNT(*) FROM cases WHERE user_side IS NULL OR user_side = ''")
        cases_without_user_side = cursor.fetchone()[0]
        
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
            'cases_without_user_side': cases_without_user_side,
            'upcoming_hearings': upcoming_hearings
        }

    def mark_multiple_cases_as_reviewed(self, cinos: List[str]) -> int:
        """Mark multiple cases as reviewed for bulk operations"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            marked_count = 0
            
            for cino in cinos:
                cursor.execute("""
                UPDATE cases
                SET is_changed = FALSE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE cino = ?
                """, (cino,))
                
                if cursor.rowcount > 0:
                    marked_count += 1
                    
                # Record in history
                cursor.execute("""
                INSERT INTO case_history (cino, field_name, old_value, new_value)
                VALUES (?, 'bulk_marked_reviewed', 'pending', 'reviewed')
                """, (cino,))
                    
            conn.commit()
            conn.close()
            
            print(f"✅ Marked {marked_count} cases as reviewed")
            return marked_count
            
        except Exception as e:
            print(f"Error marking multiple cases as reviewed: {e}")
            return 0

    def remove_from_reviewed_keep_notes(self, cinos: List[str]) -> int:
        """Remove cases from reviewed section but keep their notes"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            removed_count = 0
            
            for cino in cinos:
                # Mark as changed (removes from reviewed) but keep notes
                cursor.execute("""
                UPDATE cases
                SET is_changed = TRUE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE cino = ? AND is_changed = FALSE
                """, (cino,))
                
                if cursor.rowcount > 0:
                    removed_count += 1
                    
                # Record in history
                cursor.execute("""
                INSERT INTO case_history (cino, field_name, old_value, new_value)
                VALUES (?, 'removed_from_reviewed', 'reviewed', 'pending')
                """, (cino,))
                    
            conn.commit()
            conn.close()
            
            print(f"✅ Removed {removed_count} cases from reviewed (keeping notes)")
            return removed_count
            
        except Exception as e:
            print(f"Error removing cases from reviewed: {e}")
            return 0

    def update_case_user_side(self, cino: str, user_side: str) -> bool:
        """Update case user side (petitioner/respondent)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
            UPDATE cases
            SET user_side = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE cino = ?
            """, (user_side, cino))
            
            # Record the change in history
            cursor.execute("""
            INSERT INTO case_history (cino, field_name, old_value, new_value)
            VALUES (?, 'user_side_updated', '', ?)
            """, (cino, user_side))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            
            if success:
                print(f"✅ Updated user side for case {cino}: {user_side}")
            return success
            
        except Exception as e:
            print(f"Error updating user side: {e}")
            return False

    def _row_to_dict(self, row: tuple) -> Dict:
        """Convert database row to dictionary"""
        if not row:
            return None
            
        columns = [
            'id', 'cino', 'case_no', 'petparty_name', 'resparty_name',
            'establishment_name', 'state_name', 'district_name', 'date_next_list',
            'date_last_list', 'purpose_name', 'type_name', 'court_no_desg_name',
            'disp_name', 'updated_at', 'user_notes', 'is_changed', 'change_summary',
            'raw_data', 'user_side', 'reg_no', 'reg_year', 'date_of_decision'
        ]

        
        result = dict(zip(columns, row))
        result['is_changed'] = bool(result['is_changed'])
        return result

    def delete_all_cases_permanently(self) -> Dict[str, int]:
        """Permanently delete all cases and history from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get counts before deletion
            cursor.execute("SELECT COUNT(*) FROM cases")
            cases_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM case_history")
            history_count = cursor.fetchone()[0]
            
            # Delete all data permanently
            cursor.execute("DELETE FROM case_history")
            cursor.execute("DELETE FROM cases")
            
            # Reset auto-increment counters
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='cases'")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='case_history'")
            
            conn.commit()
            conn.close()
            
            print(f"🗑️ All cases deleted permanently: {cases_count} cases, {history_count} history records")
            
            return {
                'cases_deleted': cases_count,
                'history_deleted': history_count,
                'total_deleted': cases_count + history_count
            }
            
        except Exception as e:
            print(f"Error deleting all cases: {e}")
            return {
                'cases_deleted': 0,
                'history_deleted': 0,
                'total_deleted': 0,
                'error': str(e)
            }

    def backup_data_before_clear(self, backup_path: str = None) -> str:
        """Create a backup of all data before clearing"""
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

    def clear_all_data(self) -> Dict[str, int]:
        """Clear all case data from the database"""
        return self.delete_all_cases_permanently()

    def update_case_purpose(self, cino: str, purpose: str) -> bool:
        """Update case purpose"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
            UPDATE cases
            SET purpose_name = ?, updated_at = CURRENT_TIMESTAMP
            WHERE cino = ?
            """, (purpose, cino))
            
            # Record the change in history
            cursor.execute("""
            INSERT INTO case_history (cino, field_name, old_value, new_value)
            VALUES (?, 'purpose_updated', '', ?)
            """, (cino, purpose))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            
            if success:
                print(f"✅ Updated purpose for case {cino}: {purpose}")
            return success
            
        except Exception as e:
            print(f"Error updating purpose: {e}")
            return False

    def get_changed_cases(self) -> List[Dict]:
        """Get cases that have changes (is_changed = TRUE)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        SELECT * FROM cases
        WHERE is_changed = TRUE
        ORDER BY updated_at DESC
        """)
        cases = cursor.fetchall()
        conn.close()
        return [self._row_to_dict(case) for case in cases]

    def update_case_hearing_date(self, cino: str, hearing_date: str) -> bool:
        """Update case hearing date"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
            UPDATE cases
            SET date_next_list = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE cino = ?
            """, (hearing_date, cino))
            
            # Record the change in history
            cursor.execute("""
            INSERT INTO case_history (cino, field_name, old_value, new_value)
            VALUES (?, 'hearing_date_updated', '', ?)
            """, (cino, hearing_date))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            
            if success:
                print(f"✅ Updated hearing date for case {cino}: {hearing_date}")
            return success
            
        except Exception as e:
            print(f"Error updating hearing date: {e}")
            return False

    def update_case_hearing_date_with_history(self, cino, new_hearing_date, notes):
        """Update hearing date with proper fallback logic for last hearing date"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Step 1: Get current next hearing date from database
            cursor.execute("SELECT date_next_list, date_last_list FROM cases WHERE cino = ?", (cino,))
            result = cursor.fetchone()
            
            prev_next_hearing = None
            current_last_hearing = None
            
            if result:
                prev_next_hearing = result[0] # Current next hearing becomes last hearing
                current_last_hearing = result[1] # Current last hearing (for fallback)
                print(f"📅 DB - Current Next: {prev_next_hearing}, Current Last: {current_last_hearing}")

            # Step 2: Fallback to mycases.txt if no next hearing date in database
            if not prev_next_hearing or prev_next_hearing in ['', 'Not set', 'Not scheduled']:
                print("🔍 No next hearing in DB, checking mycases.txt...")
                try:
                    # Check if mycases.txt exists
                    mycases_path = 'data/myCases.txt'
                    if os.path.exists(mycases_path):
                        with open(mycases_path, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                        
                        # Parse different formats
                        if content:
                            try:
                                # Try JSON format first
                                parsed = json.loads(content)
                                cases_list = []
                                if isinstance(parsed, list):
                                    if all(isinstance(item, str) for item in parsed):
                                        cases_list = [json.loads(item) for item in parsed]
                                    elif all(isinstance(item, dict) for item in parsed):
                                        cases_list = parsed
                                elif isinstance(parsed, dict):
                                    cases_list = [parsed]
                            except json.JSONDecodeError:
                                # Try line-by-line format
                                cases_list = []
                                for line in content.splitlines():
                                    if line.strip() and cino in line:
                                        try:
                                            case_data = json.loads(line.strip())
                                            cases_list.append(case_data)
                                        except json.JSONDecodeError:
                                            continue
                            
                            # Find the case by CINO
                            for case_data in cases_list:
                                if case_data.get('cino') == cino:
                                    mycases_next_date = case_data.get('date_next_list', '')
                                    mycases_last_date = case_data.get('date_last_list', '')
                                    
                                    if mycases_next_date and mycases_next_date not in ['', 'Not set', 'Not scheduled']:
                                        prev_next_hearing = mycases_next_date
                                        print(f"📄 Found in mycases.txt - Next: {mycases_next_date}")
                                    elif mycases_last_date and mycases_last_date not in ['', 'Not set']:
                                        prev_next_hearing = mycases_last_date
                                        print(f"📄 Using last date from mycases.txt: {mycases_last_date}")
                                    break
                
                except Exception as fallback_error:
                    print(f"⚠️ Fallback to mycases.txt failed: {fallback_error}")

            # Step 3: Final fallback to current last hearing date
            if not prev_next_hearing and current_last_hearing:
                prev_next_hearing = current_last_hearing
                print(f"🔄 Using current last hearing as fallback: {current_last_hearing}")

            # Step 4: Update the database
            cursor.execute("""
            UPDATE cases SET
                date_next_list = ?,
                date_last_list = ?,
                user_notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE cino = ?
            """, (new_hearing_date, prev_next_hearing, notes, cino))

            # Step 5: Save notes history for the previous date
            if notes and prev_next_hearing:
                cursor.execute("""
                INSERT INTO case_history (cino, field_name, old_value, new_value)
                VALUES (?, 'notes_for_date', ?, ?)
                """, (cino, prev_next_hearing, notes))
                print(f"📝 Saved notes for date: {prev_next_hearing}")

            # Step 6: Record the hearing date change
            cursor.execute("""
            INSERT INTO case_history (cino, field_name, old_value, new_value)
            VALUES (?, 'hearing_date_updated', ?, ?)
            """, (cino, prev_next_hearing or 'No previous date', new_hearing_date))

            conn.commit()
            conn.close()
            
            print(f"✅ Updated hearing date: {prev_next_hearing} → {new_hearing_date}")
            return True

        except Exception as e:
            print(f"❌ Error updating hearing date with history: {e}")
            return False

    def get_case_notes_history(self, cino: str) -> List[Dict]:
        """Get notes history for a case grouped by hearing dates"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT old_value as hearing_date, new_value as notes, changed_at
            FROM case_history
            WHERE cino = ? AND field_name = 'notes_for_date'
            ORDER BY changed_at DESC
            """, (cino,))
            
            history = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'date': row[0],
                    'notes': row[1],
                    'timestamp': row[2]
                }
                for row in history
            ]
            
        except Exception as e:
            print(f"Error getting notes history: {e}")
            return []

    def update_case_field(self, cino: str, field_name: str, field_value: str) -> bool:
        """Update any case field"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Valid fields that can be updated
            valid_fields = [
                'petparty_name', 'resparty_name', 'purpose_name',
                'type_name', 'court_no_desg_name', 'user_side'
            ]

            if field_name not in valid_fields:
                return False

            cursor.execute(f"""
            UPDATE cases
            SET {field_name} = ?, updated_at = CURRENT_TIMESTAMP
            WHERE cino = ?
            """, (field_value, cino))
            
            # Record the change
            cursor.execute("""
            INSERT INTO case_history (cino, field_name, old_value, new_value)
            VALUES (?, ?, '', ?)
            """, (cino, f'{field_name}_updated', field_value))
            
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success
            
        except Exception as e:
            print(f"Error updating case field: {e}")
            return False

    def get_notes_by_date(self, cino, hearing_date):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        SELECT new_value FROM case_history WHERE cino = ? AND field_name = 'notes_for_date' AND old_value = ?
        ORDER BY id DESC
        """, (cino, hearing_date))
        notes = [row[0] for row in cursor.fetchall()]
        conn.close()
        return notes
    
    # function to get active cases and dispose cases using date_of_decision
    def get_active_and_disposed_cases(self) -> Dict[str, List[Dict]]:
        """Get active cases and disposed cases based on date_of_decision"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Active cases: date_of_decision is NULL or empty
            cursor.execute("""
            SELECT * FROM cases
            WHERE (date_of_decision IS NULL OR date_of_decision = '')
            ORDER BY updated_at DESC
            """)
            active_cases = cursor.fetchall()
            
            # Disposed cases: date_of_decision is set
            cursor.execute("""
            SELECT * FROM cases
            WHERE date_of_decision IS NOT NULL AND date_of_decision != ''
            ORDER BY date_of_decision DESC
            """)
            disposed_cases = cursor.fetchall()
            
            conn.close()
            
            return {
                'active_cases': [self._row_to_dict(case) for case in active_cases],
                'disposed_cases': [self._row_to_dict(case) for case in disposed_cases]
            }
            
        except Exception as e:
            print(f"Error getting active and disposed cases: {e}")
            return {
                'active_cases': [],
                'disposed_cases': [],
                'error': str(e)
            }

    def update_case_notes_and_mark_reviewed(self, cino: str, notes: str) -> bool:
        """Update case notes and mark as reviewed in single transaction"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Single transaction for both operations
            cursor.execute("""
                UPDATE cases 
                SET user_notes = ?, 
                    is_changed = FALSE, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE cino = ?
            """, (notes, cino))
            
            # Record both actions in history
            cursor.execute("""
                INSERT INTO case_history (cino, field_name, old_value, new_value)
                VALUES (?, 'notes_updated_and_reviewed', '', ?)
            """, (cino, notes))
            
            # Commit single transaction
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            
            if success:
                print(f"✅ Updated notes and marked case {cino} as reviewed")
            
            return success
            
        except Exception as e:
            print(f"❌ Error updating case notes and marking reviewed: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return False
