from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import secrets
import time
from datetime import datetime
from database import CaseDatabase
from calendar_utils import (
    get_court_events_for_deletion,
    delete_court_events_by_summary_or_description,
    delete_events_by_ids,
    complete_system_cleanup,
    clear_local_case_files
)

app = Flask(__name__)

app.static_folder = 'static'
app.static_url_path = '/static'

def get_or_create_secret_key():
    """Get existing secret key or create a new one"""
    secret_file = 'secret.key'
    if os.path.exists(secret_file):
        with open(secret_file, 'r') as f:
            return f.read().strip()
    else:
        # Generate new secret key
        secret_key = secrets.token_urlsafe(32)
        with open(secret_file, 'w') as f:
            f.write(secret_key)
        print("✅ Generated new secret.key file")
        return secret_key

# In your Flask app
app.config['SECRET_KEY'] = get_or_create_secret_key()

# Initialize database
os.makedirs('data', exist_ok=True)
db = CaseDatabase()

@app.route('/')
def dashboard():
    """Main dashboard showing all cases"""
    try:
        cases = db.get_all_cases()
        changed_cases = [case for case in cases if case['is_changed']]
        reviewed_cases = db.get_reviewed_cases_with_notes()
        
        # Get counts for badges
        counts = db.get_case_counts()
        
        return render_template('index.html',
                             cases=cases,
                             changed_cases=changed_cases,
                             reviewed_cases=reviewed_cases,
                             total_cases=counts['total_cases'],
                             changed_cases_count=counts['changed_cases'],
                             reviewed_cases_count=counts['reviewed_cases'],
                             petitioner_cases_count=counts['petitioner_cases'],
                             respondent_cases_count=counts['respondent_cases'],
                             upcoming_hearings_count=counts['upcoming_hearings'],
                             current_date=datetime.now().strftime('%B %d, %Y'))
    except Exception as e:
        print(f"Dashboard error: {e}")
        return render_template('index.html',
                             cases=[],
                             changed_cases=[],
                             reviewed_cases=[],
                             total_cases=0,
                             changed_cases_count=0,
                             reviewed_cases_count=0,
                             petitioner_cases_count=0,
                             respondent_cases_count=0,
                             upcoming_hearings_count=0,
                             current_date=datetime.now().strftime('%B %d, %Y'),
                             error=str(e))
@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload and process daily myCases.txt file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if file and file.filename.endswith('.txt'):
            file_path = os.path.join('data', 'myCases.txt')
            file.save(file_path)

            stats = db.process_daily_file(file_path)

            if 'error' in stats:
                return jsonify({'error': f'Processing failed: {stats["error"]}'}), 500

            return jsonify({
                'message': 'File processed successfully',
                'stats': stats
            })

        return jsonify({'error': 'Invalid file type. Please upload a .txt file'}), 400

    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/case/<cino>')
def case_detail(cino):
    """Case detail page for editing"""
    try:
        case = db.get_case_by_cino(cino)
        if not case:
            return render_template('error.html',
                                 message="Case not found",
                                 error_code=404), 404

        return render_template('case_detail.html', case=case)

    except Exception as e:
        print(f"Case detail error: {e}")
        return render_template('error.html',
                             message=f"Error loading case: {str(e)}",
                             error_code=500), 500

@app.route('/case/<cino>/update', methods=['POST'])
def update_case(cino):
    """Update case notes and other fields"""
    try:
        data = request.json
        notes = data.get('notes', '')
        other_updates = data.get('updates', {})

        success = db.update_case_notes(cino, notes, other_updates)

        if success:
            db.mark_case_reviewed(cino)
            return jsonify({'message': 'Case updated successfully'})
        else:
            return jsonify({'error': 'Failed to update case'}), 500

    except Exception as e:
        print(f"Update case error: {e}")
        return jsonify({'error': f'Update failed: {str(e)}'}), 500

@app.route('/case/<cino>/mark_reviewed', methods=['POST'])
def mark_reviewed(cino):
    """Mark case as reviewed"""
    try:
        db.mark_case_reviewed(cino)
        return jsonify({'message': 'Case marked as reviewed'})

    except Exception as e:
        print(f"Mark reviewed error: {e}")
        return jsonify({'error': f'Failed to mark as reviewed: {str(e)}'}), 500

@app.route('/create_case', methods=['GET', 'POST'])
def create_case():
    """Create a new case manually"""
    if request.method == 'GET':
        return render_template('create_case.html')
    
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['cino', 'case_no', 'petparty_name', 'resparty_name', 'type_name']
        for field in required_fields:
            if not data.get(field, '').strip():
                return jsonify({'error': f'{field} is required'}), 400
        
        # Create case data
        case_data = {
            'cino': data.get('cino', '').strip(),
            'case_no': data.get('case_no', '').strip(),
            'petparty_name': data.get('petparty_name', '').strip(),
            'resparty_name': data.get('resparty_name', '').strip(),
            'establishment_name': data.get('establishment_name', '').strip(),
            'state_name': data.get('state_name', '').strip(),
            'district_name': data.get('district_name', '').strip(),
            'date_next_list': data.get('date_next_list', '').strip(),
            'date_last_list': data.get('date_last_list', '').strip(),
            'purpose_name': data.get('purpose_name', '').strip(),
            'type_name': data.get('type_name', '').strip(),
            'court_no_desg_name': data.get('court_no_desg_name', '').strip(),
            'disp_name': data.get('disp_name', '').strip(),
            'user_notes': data.get('user_notes', '').strip(),
            'user_side': data.get('user_side', '').strip(),
            'reg_no': data.get('reg_no'),
            'reg_year': data.get('reg_year')
        }
        
        success, message = db.create_new_case(case_data)
        
        if success:
            return jsonify({'message': 'Case created successfully', 'cino': case_data['cino']})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        print(f"Create case error: {e}")
        return jsonify({'error': f'Failed to create case: {str(e)}'}), 500

@app.route('/save_all', methods=['POST'])
def save_all():
    """Save all pending changes"""
    try:
        data = request.json
        updates = data.get('updates', [])

        success_count = 0
        for update in updates:
            cino = update.get('cino')
            notes = update.get('notes', '')
            other_fields = update.get('fields', {})

            if db.update_case_notes(cino, notes, other_fields):
                db.mark_case_reviewed(cino)
                success_count += 1

        return jsonify({'message': f'Successfully saved {success_count} of {len(updates)} cases'})

    except Exception as e:
        print(f"Save all error: {e}")
        return jsonify({'error': f'Save all failed: {str(e)}'}), 500

@app.route('/create_calendar_events', methods=['POST'])
def create_calendar_events():
    """Create Google Calendar events with notes"""
    try:
        data = request.json
        filter_type = data.get('filter', 'all')

        if filter_type == 'reviewed_only':
            # Use provided cases from request
            cases = data.get('cases', [])
        else:
            # Get all cases as before
            cases = db.get_all_cases()

        # Filter cases with valid dates
        valid_cases = []
        for case in cases:
            if (case.get('date_next_list') and
                case['date_next_list'] not in ['Not set', '', None]):
                valid_cases.append(case)

        if not valid_cases:
            return jsonify({
                'error': 'No cases with valid dates found',
                'created': 0,
                'failed': 0,
                'skipped': 0,
                'total_cases': len(cases)
            }), 400

        # Create calendar events
        from calendar_utils import create_google_calendar_events_for_cases
        result = create_google_calendar_events_for_cases(valid_cases)

        # Check for errors
        if 'error' in result:
            return jsonify({
                'error': result['error'],
                'created': result.get('created', 0),
                'failed': result.get('failed', 0),
                'skipped': result.get('skipped', 0)
            }), 500

        return jsonify({
            'message': f"Calendar updated successfully! {result['created']} events created",
            'created': result['created'],
            'failed': result['failed'],
            'skipped': result['skipped'],
            'total_processed': result['total_processed']
        })

    except Exception as e:
        print(f"Calendar creation error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Calendar creation failed: {str(e)}'}), 500

@app.route('/calendar_progress')
def calendar_progress():
    """Get calendar creation progress"""
    try:
        cases = db.get_all_cases()

        stats = {
            'total_cases': len(cases),
            'cases_with_notes': len([c for c in cases if c.get('user_notes', '').strip()]),
            'cases_with_dates': len([c for c in cases if c.get('date_next_list') and c['date_next_list'] not in ['Not set', '', None]]),
            'ready_for_calendar': len([c for c in cases if (
                c.get('date_next_list') and
                c['date_next_list'] not in ['Not set', '', None] and
                c.get('user_notes', '').strip()
            )])
        }

        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cases/upcoming_hearings')
def upcoming_hearings():
    """Get cases with upcoming hearings"""
    try:
        cases = db.get_all_cases()
        from datetime import datetime, timedelta
        
        today = datetime.now().date()
        upcoming_cases = []
        
        for case in cases:
            if case.get('date_next_list'):
                try:
                    # Parse the date (assuming format YYYY-MM-DD)
                    hearing_date = datetime.strptime(case['date_next_list'], '%Y-%m-%d').date()
                    if hearing_date >= today:
                        upcoming_cases.append(case)
                except ValueError:
                    continue
        
        # Sort by hearing date
        upcoming_cases.sort(key=lambda x: x.get('date_next_list', ''))
        return jsonify(upcoming_cases)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cases/petitioner')
def petitioner_cases():
    """Get cases where user is petitioner"""
    try:
        cases = db.get_all_cases()
        petitioner_cases = [case for case in cases if case.get('user_side') == 'petitioner']
        return jsonify(petitioner_cases)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cases/respondent')
def respondent_cases():
    """Get cases where user is respondent"""
    try:
        cases = db.get_all_cases()
        respondent_cases = [case for case in cases if case.get('user_side') == 'respondent']
        return jsonify(respondent_cases)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cases/reviewed')
def reviewed_cases_api():
    """Get reviewed cases"""
    try:
        reviewed = db.get_reviewed_cases_with_notes()
        return jsonify(reviewed)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/reviewed_cases')
def reviewed_cases():
    """Get cases that have been reviewed and have notes"""
    try:
        reviewed = db.get_reviewed_cases_with_notes()
        return render_template('reviewed_cases.html', cases=reviewed)

    except Exception as e:
        print(f"Reviewed cases error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/calendar_events_preview')
def calendar_events_preview():
    """Preview calendar events that will be deleted"""
    try:
        # Get court events for preview
        events = get_court_events_for_deletion()

        return jsonify({
            'events': events[:50], # Limit to first 50 for preview
            'total_count': len(events),
            'message': f'Found {len(events)} court events that can be deleted'
        })

    except Exception as e:
        print(f"Calendar preview error: {e}")
        return jsonify({'error': f'Failed to preview events: {str(e)}'}), 500

@app.route('/delete_calendar_events', methods=['POST'])
def delete_calendar_events():
    """Delete all court calendar events with enhanced debugging"""
    try:
        print("🚀 Starting calendar deletion process...")

        data = request.json
        deletion_method = data.get('method', 'auto')
        event_ids = data.get('event_ids', [])

        if deletion_method == 'by_ids' and event_ids:
            print(f"🎯 Deleting specific events by ID: {len(event_ids)} events")
            result = delete_events_by_ids(event_ids)
        else:
            print("🔄 Auto-deleting all court events")
            result = delete_court_events_by_summary_or_description()

        # Check for errors in result
        if 'error' in result:
            print(f"❌ Deletion failed: {result['error']}")
            return jsonify({
                'error': result['error'],
                'deleted': result.get('deleted', 0),
                'failed': result.get('failed', 0),
                'total_processed': result.get('total_processed', 0)
            }), 500

        success_message = f"Successfully processed {result['total_processed']} events: {result['deleted']} deleted, {result['failed']} failed"
        print(f"✅ {success_message}")

        return jsonify({
            'message': success_message,
            'deleted': result['deleted'],
            'failed': result['failed'],
            'total_processed': result['total_processed'],
            'batches_processed': result.get('batches_processed', 1)
        })

    except Exception as e:
        error_msg = f'Calendar deletion failed: {str(e)}'
        print(f"💥 {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500

@app.route('/calendar_deletion_progress')
def calendar_deletion_progress():
    """Get real-time progress of calendar deletion (for future websocket implementation)"""
    try:
        # This would be enhanced with websockets for real-time updates
        # For now, return current status
        return jsonify({
            'status': 'idle',
            'message': 'No deletion in progress'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/complete_system_cleanup', methods=['POST'])
def complete_system_cleanup_route():
    """Complete system cleanup: calendar + database + files"""
    try:
        print("🧹 Starting complete system cleanup...")

        # Perform complete cleanup
        result = complete_system_cleanup()

        if result.get('total_success', False):
            success_message = "Complete system cleanup successful!"

            # Build detailed message
            calendar_deleted = result.get('calendar_deletion', {}).get('deleted', 0)
            database_deleted = result.get('database_cleanup', {}).get('cases_deleted', 0)
            files_deleted = result.get('file_cleanup', {}).get('total_deleted', 0)

            detailed_message = f"""
🎉 System Cleanup Complete!
📅 Calendar Events: {calendar_deleted} deleted
🗄️ Database Records: {database_deleted} deleted
📁 Local Files: {files_deleted} deleted
{f"💾 Backup saved: {result.get('backup_created', 'N/A')}" if result.get('backup_created') else ""}
"""

            return jsonify({
                'message': success_message,
                'detailed_message': detailed_message,
                'calendar_deleted': calendar_deleted,
                'database_deleted': database_deleted,
                'files_deleted': files_deleted,
                'backup_path': result.get('backup_created'),
                'success': True
            })

        else:
            # Partial success or failure
            error_parts = []
            if 'error' in result.get('calendar_deletion', {}):
                error_parts.append(f"Calendar: {result['calendar_deletion']['error']}")
            if 'error' in result.get('database_cleanup', {}):
                error_parts.append(f"Database: {result['database_cleanup']['error']}")
            if result.get('file_cleanup', {}).get('total_failed', 0) > 0:
                error_parts.append(f"Files: {result['file_cleanup']['total_failed']} failed")

            return jsonify({
                'error': 'Partial cleanup failure: ' + '; '.join(error_parts),
                'result': result,
                'success': False
            }), 500

    except Exception as e:
        error_msg = f'Complete cleanup failed: {str(e)}'
        print(f"💥 {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': error_msg, 'success': False}), 500

@app.route('/clear_local_data', methods=['POST'])
def clear_local_data():
    """Clear only local database and files (not calendar)"""
    try:
        print("🗑️ Clearing local data only...")

        # Create backup first
        db = CaseDatabase()
        backup_path = db.backup_data_before_clear()

        # Clear database
        db_result = db.clear_all_data()

        # Clear local files
        file_result = clear_local_case_files()

        return jsonify({
            'message': f'Local data cleared: {db_result.get("cases_deleted", 0)} cases, {file_result.get("total_deleted", 0)} files',
            'database_result': db_result,
            'file_result': file_result,
            'backup_path': backup_path
        })

    except Exception as e:
        print(f"Clear local data error: {e}")
        return jsonify({'error': f'Failed to clear local data: {str(e)}'}), 500

@app.route('/reviewed_cases_data')
def reviewed_cases_data():
    """Get reviewed cases data for calendar creation"""
    try:
        reviewed_cases = db.get_reviewed_cases_with_notes()
        return jsonify(reviewed_cases)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting e-Courts Case Management System...")
    print(f"Secret key configured: {'Yes' if app.secret_key else 'No'}")
    app.run(debug=True, port=5000, host='0.0.0.0')