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
        secret_key = secrets.token_urlsafe(32)
        with open(secret_file, 'w') as f:
            f.write(secret_key)
        print("✅ Generated new secret.key file")
        return secret_key

app.config['SECRET_KEY'] = get_or_create_secret_key()

# Initialize database
os.makedirs('data', exist_ok=True)
db = CaseDatabase()


@app.route('/')
def index():
    """Main entry point - redirect based on data availability"""
    try:
        cases = db.get_all_cases()
        if not cases:
            return redirect(url_for('upload_page'))
        else:
            return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"Index error: {e}")
        return redirect(url_for('upload_page'))

@app.route('/dashboard')
def dashboard():
    """Law Firm Case Management Dashboard - Updated"""
    try:
        print("🏠 Accessing dashboard...")
        cases = db.get_all_cases()
        # Sort by next hearing date descending
        cases.sort(key=lambda x: x.get('date_next_list', ''), reverse=True)  

        print(f"📊 Retrieved {len(cases)} total cases")

        if not cases or len(cases) == 0:
            print("⚠️ No cases found, redirecting to upload page")
            return redirect(url_for('upload_page'))

        # Get different case categories
        try:
            changed_cases = db.get_changed_cases()  # New method
            print(f"⚠️ Changed cases: {len(changed_cases)}")
        except Exception as e:
            print(f"⚠️ Error getting changed cases: {e}")
            changed_cases = [case for case in cases if case.get('is_changed', False)]

        try:
            reviewed_cases = db.get_reviewed_cases_with_notes()
            print(f"✅ Reviewed cases: {len(reviewed_cases)}")
        except Exception as e:
            print(f"⚠️ Error getting reviewed cases: {e}")
            reviewed_cases = []

        # Get upcoming cases
        upcoming_cases = []
        try:
            from datetime import datetime
            today = datetime.now().date()
            for case in cases:
                if case.get('date_next_list'):
                    try:
                        hearing_date = datetime.strptime(case['date_next_list'], '%Y-%m-%d').date()
                        if hearing_date >= today:
                            upcoming_cases.append(case)
                    except ValueError:
                        continue
            upcoming_cases.sort(key=lambda x: x.get('date_next_list', ''))
            print(f"📅 Upcoming cases: {len(upcoming_cases)}")
        except Exception as e:
            print(f"⚠️ Error processing upcoming cases: {e}")
            upcoming_cases = []

        # Get counts
        try:
            counts = db.get_case_counts()
            print(f"📊 Counts retrieved: {counts}")
        except Exception as e:
            print(f"⚠️ Error getting counts: {e}")
            counts = {
                'total_cases': len(cases),
                'changed_cases': len(changed_cases),
                'reviewed_cases': len(reviewed_cases),
                'upcoming_hearings': len(upcoming_cases)
            }

        print("🎯 Rendering dashboard template...")
        return render_template('index.html',
                             cases=cases,
                             changed_cases=changed_cases,
                             reviewed_cases=reviewed_cases,
                             upcoming_cases=upcoming_cases,
                             total_cases=counts['total_cases'],
                             changed_cases_count=counts['changed_cases'],
                             reviewed_cases_count=counts['reviewed_cases'],
                             upcoming_hearings_count=counts['upcoming_hearings'],
                             current_date=datetime.now().strftime('%B %d, %Y'))

    except Exception as e:
        print(f"💥 Dashboard error: {e}")
        import traceback
        traceback.print_exc()
        return render_template('error.html',
                             error_message=str(e),
                             error_details="Dashboard failed to load.")

@app.route('/upload_page')
def upload_page():
    """Upload page for myCases.txt files"""
    return render_template('upload_page.html')

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
            os.makedirs('data', exist_ok=True)
            file_path = os.path.join('data', 'myCases.txt')
            
            file.save(file_path)
            print(f"✅ File saved to: {file_path}")
            
            stats = db.process_daily_file(file_path)
            
            if 'error' in stats:
                return jsonify({'error': f'Processing failed: {stats["error"]}'}), 500
            
            return jsonify({
                'message': 'File processed successfully',
                'stats': stats,
                'redirect_url': '/dashboard'
            })
            
        return jsonify({'error': 'Invalid file type. Please upload a .txt file'}), 400
        
    except Exception as e:
        print(f"Upload error: {e}")
        import traceback
        traceback.print_exc()
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
        
        # Get notes history
        case['notes_history'] = db.get_case_notes_history(cino)
        
        return render_template('case_detail.html', case=case)
    except Exception as e:
        print(f"Case detail error: {e}")
        return render_template('error.html',
                             message=f"Error loading case: {str(e)}",
                             error_code=500), 500

@app.route('/case/<cino>/update', methods=['POST'])
def update_case(cino):
    """Update case - Always mark as reviewed when saved"""
    try:
        print(f"📝 Updating case {cino}...")
        
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        notes = data.get('notes', '')
        
        print(f"📝 Notes: '{notes[:50]}...'")
        
        # Update case notes
        success = db.update_case_notes(cino, notes)
        
        if success:
            # Always mark as reviewed when saving
            db.mark_case_as_reviewed(cino)
            print(f"✅ Case {cino} marked as reviewed")
            
            return jsonify({
                'message': 'Case marked as reviewed successfully',
                'has_notes': bool(notes.strip()),
                'marked_as_reviewed': True
            })
        else:
            return jsonify({'error': 'Failed to update case'}), 500
            
    except Exception as e:
        print(f"❌ Update case error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Update failed: {str(e)}'}), 500

@app.route('/case/<cino>/update_user_side', methods=['POST'])
def update_user_side(cino):
    """Update case user side (petitioner/respondent)"""
    try:
        data = request.json
        user_side = data.get('user_side', '')
        
        if user_side not in ['petitioner', 'respondent']:
            return jsonify({'error': 'Invalid user side. Must be petitioner or respondent'}), 400
        
        success = db.update_case_user_side(cino, user_side)
        
        if success:
            return jsonify({
                'message': 'User side updated successfully',
                'user_side': user_side
            })
        else:
            return jsonify({'error': 'Failed to update user side'}), 500
            
    except Exception as e:
        print(f"Update user side error: {e}")
        return jsonify({'error': f'Update failed: {str(e)}'}), 500

@app.route('/case/<cino>/update_hearing_date', methods=['POST'])
def update_hearing_date(cino):
    """Update case hearing date"""
    try:
        data = request.json
        hearing_date = data.get('hearing_date', '')
        
        if hearing_date:
            try:
                from datetime import datetime
                datetime.strptime(hearing_date, '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        success = db.update_case_hearing_date(cino, hearing_date)
        
        if success:
            return jsonify({
                'message': 'Hearing date updated successfully',
                'hearing_date': hearing_date or None
            })
        else:
            return jsonify({'error': 'Failed to update hearing date'}), 500
            
    except Exception as e:
        print(f"Update hearing date error: {e}")
        return jsonify({'error': f'Update failed: {str(e)}'}), 500

@app.route('/add_case', methods=['GET', 'POST'])
def add_case():
    """Add new case manually for law firm"""
    if request.method == 'GET':
        return render_template('add_case.html')
    
    try:
        data = request.json
        # Validate required fields
        required_fields = ['cino', 'case_no', 'petparty_name', 'resparty_name']
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
            return jsonify({'message': 'Case added successfully', 'cino': case_data['cino']})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        print(f"Add case error: {e}")
        return jsonify({'error': f'Failed to add case: {str(e)}'}), 500

@app.route('/toggle_case_selection', methods=['POST'])
def toggle_case_selection():
    """Toggle case selection for bulk operations"""
    try:
        data = request.json
        cinos = data.get('cinos', [])
        action = data.get('action', 'mark_reviewed')  # mark_reviewed, remove_from_reviewed
        
        if not cinos:
            return jsonify({'error': 'No cases specified'}), 400
            
        if action == 'mark_reviewed':
            success_count = db.mark_multiple_cases_as_reviewed(cinos)
            return jsonify({
                'message': f'Successfully marked {success_count} cases as reviewed',
                'marked_count': success_count
            })
        elif action == 'remove_from_reviewed':
            removed_count = db.remove_from_reviewed_keep_notes(cinos)
            return jsonify({
                'message': f'Successfully removed {removed_count} cases from reviewed section',
                'removed_count': removed_count
            })
        else:
            return jsonify({'error': 'Invalid action'}), 400
        
    except Exception as e:
        print(f"Toggle case selection error: {e}")
        return jsonify({'error': f'Operation failed: {str(e)}'}), 500

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
                db.mark_case_as_reviewed(cino)
                success_count += 1
        
        return jsonify({'message': f'Successfully saved {success_count} of {len(updates)} cases'})
        
    except Exception as e:
        print(f"Save all error: {e}")
        return jsonify({'error': f'Save all failed: {str(e)}'}), 500

@app.route('/create_calendar_events', methods=['POST'])
def create_calendar_events():
    """Create Google Calendar events - FIXED to handle selected cases only"""
    try:
        print("🔍 Starting calendar creation...")
        
        from calendar_utils import google_calendar_authenticate
        creds = google_calendar_authenticate()
        
        if not creds:
            return jsonify({
                'error': 'Google Calendar authentication failed.',
                'suggestion': 'Please check your credentials and try again'
            }), 401
        
        data = request.json
        filter_type = data.get('filter', 'all')
        scope = data.get('scope', 'all')
        
        print(f"📊 Filter type: {filter_type}, Scope: {scope}")
        
        # FIXED: Proper case selection logic with enhanced data
        if filter_type in ['selected_cases_only'] or scope == 'selected':
            # Use ONLY the cases sent from frontend
            cases = data.get('cases', [])
            print(f"📋 Using selected cases from frontend: {len(cases)} cases")
            
            # Log the CINOs for debugging
            if cases:
                cinos = [case.get('cino') for case in cases]
                print(f"📝 Selected CINOs: {cinos[:5]}..." if len(cinos) > 5 else f"📝 Selected CINOs: {cinos}")
        
        elif filter_type in ['current_tab_all'] or scope == 'all':
            # Use all cases sent from frontend (for current tab)
            cases = data.get('cases', [])
            if not cases:
                # Fallback to database if no cases provided
                cases = db.get_all_cases()
            print(f"📋 Using all cases: {len(cases)} cases")
        
        else:
            # FIXED: Fallback to all cases from database but enhance with fresh data
            print("📋 Using fallback - getting all database cases with fresh data...")
            cases = db.get_all_cases()
            print(f"📋 Fallback to all database cases: {len(cases)} cases")
        
        # ENHANCED: Ensure all cases have complete data for calendar description
        enhanced_cases = []
        for case in cases:
            try:
                cino = case.get('cino', '')
                
                # Get fresh data from database for this case to ensure we have latest user_side
                fresh_case = db.get_case_by_cino(cino)
                if fresh_case:
                    # Merge frontend data with fresh database data, prioritizing database for user_side
                    enhanced_case = {
                        'cino': fresh_case.get('cino', ''),
                        'case_no': fresh_case.get('case_no', ''),
                        'petparty_name': fresh_case.get('petparty_name', ''),
                        'resparty_name': fresh_case.get('resparty_name', ''),
                        'establishment_name': fresh_case.get('establishment_name', ''),
                        'state_name': fresh_case.get('state_name', ''),
                        'district_name': fresh_case.get('district_name', ''),
                        'date_next_list': fresh_case.get('date_next_list', ''),
                        'date_last_list': fresh_case.get('date_last_list', ''),
                        'purpose_name': fresh_case.get('purpose_name', ''),
                        'type_name': fresh_case.get('type_name', ''),
                        'court_no_desg_name': fresh_case.get('court_no_desg_name', ''),
                        'disp_name': fresh_case.get('disp_name', ''),
                        'user_notes': fresh_case.get('user_notes', ''),
                        'user_side': fresh_case.get('user_side', ''),  # Always use fresh from DB
                        'reg_no': fresh_case.get('reg_no', ''),
                        'reg_year': fresh_case.get('reg_year', ''),
                    }
                    
                    # Override with any frontend-specific data if provided
                    if 'user_notes' in case and case['user_notes']:
                        enhanced_case['user_notes'] = case['user_notes']
                    
                    enhanced_cases.append(enhanced_case)
                    
                    print(f"✅ Enhanced case {cino}: user_side='{enhanced_case.get('user_side', 'Not set')}'")
                else:
                    # If not found in DB, use original case data
                    enhanced_cases.append(case)
                    print(f"⚠️ Case {cino} not found in DB, using original data")
                    
            except Exception as enhance_error:
                print(f"⚠️ Error enhancing case {case.get('cino', 'Unknown')}: {enhance_error}")
                # Use original case data if enhancement fails
                enhanced_cases.append(case)
        
        cases = enhanced_cases
        
        if not cases:
            return jsonify({
                'error': 'No cases provided for calendar creation',
                'created': 0,
                'failed': 0,
                'skipped': 0
            }), 400
        
        print(f"📊 Final processing {len(cases)} enhanced cases...")
        
        # Debug: Print first case data
        if cases:
            first_case = cases[0]
            print(f"🔍 Sample case data:")
            print(f"   CINO: {first_case.get('cino', 'N/A')}")
            print(f"   User Side: '{first_case.get('user_side', 'Not set')}'")
            print(f"   Type Name: '{first_case.get('type_name', 'N/A')}'")
            print(f"   Reg No: '{first_case.get('reg_no', 'N/A')}'")
            print(f"   Reg Year: '{first_case.get('reg_year', 'N/A')}'")
            print(f"   Case No: '{first_case.get('case_no', 'N/A')}'")
        
        from calendar_utils import create_google_calendar_events_for_cases
        result = create_google_calendar_events_for_cases(
            cases_data=cases,
            filter_info={'type': filter_type, 'scope': scope, 'original_request': data}
        )
        
        if 'error' in result:
            return jsonify({
                'error': result['error'],
                'created': result.get('created', 0),
                'failed': result.get('failed', 0),
                'skipped': result.get('skipped', 0)
            }), 500
        
        return jsonify({
            'message': f"Calendar updated! {result['created']} events created, {result.get('updated', 0)} updated",
            'created': result['created'],
            'updated': result.get('updated', 0),
            'failed': result['failed'],
            'skipped': result['skipped'],
            'total_processed': result['total_processed']
        })
        
    except Exception as e:
        error_msg = f'Calendar creation failed: {str(e)}'
        print(f"💥 {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500
   
@app.route('/delete_selected_calendar_events', methods=['POST'])
def delete_selected_calendar_events():
    """Delete calendar events for selected cases"""
    try:
        data = request.json
        cases = data.get('cases', [])
        
        if not cases:
            return jsonify({'error': 'No cases provided'}), 400
        
        cinos = [case.get('cino') for case in cases if case.get('cino')]
        
        from calendar_utils import delete_events_by_cinos
        result = delete_events_by_cinos(cinos)
        
        return jsonify({
            'message': f'Deleted {result["deleted"]} calendar events',
            'deleted': result['deleted'],
            'failed': result['failed']
        })
        
    except Exception as e:
        return jsonify({'error': f'Delete failed: {str(e)}'}), 500

@app.route('/delete_all_cases_and_calendar', methods=['POST'])
def delete_all_cases_and_calendar():
    """Delete all cases from database and calendar events"""
    try:
        print("🧹 Starting complete deletion of all cases and calendar events...")
        
        data = request.json
        confirmation = data.get('confirmation', '')
        
        if confirmation != 'DELETE_ALL_FOREVER':
            return jsonify({
                'error': 'Invalid confirmation. Please type "DELETE_ALL_FOREVER" to confirm.'
            }), 400
        
        # Create backup first
        try:
            backup_path = db.backup_data_before_clear()
            print(f"✅ Backup created: {backup_path}")
        except Exception as backup_error:
            print(f"⚠️ Backup creation failed: {backup_error}")
            backup_path = None
        
        # Delete calendar events
        from calendar_utils import delete_court_events_by_summary_or_description
        calendar_result = delete_court_events_by_summary_or_description()
        
        # Delete all database cases
        db_result = db.delete_all_cases_permanently()
        
        # Clear local files
        from calendar_utils import clear_local_case_files
        file_result = clear_local_case_files()
        
        return jsonify({
            'message': 'All cases and calendar events deleted successfully',
            'calendar_deleted': calendar_result.get('deleted', 0),
            'cases_deleted': db_result.get('cases_deleted', 0),
            'history_deleted': db_result.get('history_deleted', 0),
            'files_deleted': file_result.get('total_deleted', 0),
            'backup_path': backup_path,
            'success': True
        })
        
    except Exception as e:
        error_msg = f'Complete deletion failed: {str(e)}'
        print(f"💥 {error_msg}")
        return jsonify({'error': error_msg, 'success': False}), 500

@app.route('/mark_multiple_as_reviewed', methods=['POST'])
def mark_multiple_as_reviewed():
    """Mark multiple cases as reviewed from All Cases tab"""
    try:
        data = request.json
        cinos = data.get('cinos', [])
        
        if not cinos:
            return jsonify({'error': 'No cases specified'}), 400
            
        marked_count = db.mark_multiple_cases_as_reviewed(cinos)
        
        return jsonify({
            'message': f'Successfully marked {marked_count} cases as reviewed',
            'marked_count': marked_count
        })
        
    except Exception as e:
        print(f"Mark multiple as reviewed error: {e}")
        return jsonify({'error': f'Failed to mark cases: {str(e)}'}), 500

@app.route('/remove_from_reviewed_only', methods=['POST'])
def remove_from_reviewed_only():
    """Remove cases from reviewed section only (keep notes)"""
    try:
        data = request.json
        cinos = data.get('cinos', [])
        
        if not cinos:
            return jsonify({'error': 'No cases specified'}), 400
            
        removed_count = db.remove_from_reviewed_keep_notes(cinos)
        
        return jsonify({
            'message': f'Successfully removed {removed_count} cases from reviewed section',
            'removed_count': removed_count
        })
        
    except Exception as e:
        print(f"Remove from reviewed only error: {e}")
        return jsonify({'error': f'Remove failed: {str(e)}'}), 500

@app.route('/mark_cases_processed', methods=['POST'])
def mark_cases_processed():
    """Mark cases as processed after calendar actions"""
    try:
        data = request.json
        cinos = data.get('cinos', [])
        action_type = data.get('action_type', 'processed')
        processed_at = data.get('processed_at')
        
        if not cinos:
            return jsonify({'error': 'No cases specified'}), 400
        
        # Mark cases as processed in database
        processed_count = db.mark_cases_as_processed(cinos, action_type, processed_at)
        
        return jsonify({
            'message': f'Successfully marked {processed_count} cases as processed',
            'processed_count': processed_count,
            'action_type': action_type
        })
        
    except Exception as e:
        print(f"Mark cases as processed error: {e}")
        return jsonify({'error': f'Failed to mark as processed: {str(e)}'}), 500


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
            'events': events[:50],  # Limit to first 50 for preview
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


@app.route('/fix_data_state', methods=['POST'])
def fix_data_state():
    """Fix existing data state for proper reviewed/pending logic"""
    try:
        fixed_count = db.fix_existing_cases_state()
        return jsonify({
            'message': f'Fixed {fixed_count} cases to proper state',
            'fixed_count': fixed_count
        })
    except Exception as e:
        return jsonify({'error': f'Fix failed: {str(e)}'}), 500

@app.route('/case/<cino>/update_purpose', methods=['POST'])
def update_case_purpose(cino):
    """Update case purpose"""
    try:
        data = request.json
        purpose = data.get('purpose', '')
        
        if not purpose.strip():
            return jsonify({'error': 'Purpose cannot be empty'}), 400
        
        success = db.update_case_purpose(cino, purpose.strip())
        
        if success:
            return jsonify({
                'message': 'Purpose updated successfully',
                'purpose': purpose.strip()
            })
        else:
            return jsonify({'error': 'Failed to update purpose'}), 500
            
    except Exception as e:
        print(f"Update purpose error: {e}")
        return jsonify({'error': f'Update failed: {str(e)}'}), 500

@app.route('/api/cases/changed')
def changed_cases_api():
    """Get changed cases"""
    try:
        changed = db.get_changed_cases()
        return jsonify(changed)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/case/<cino>/update_hearing_date_with_history', methods=['POST'])
def update_hearing_date_with_history(cino):
    """Update hearing date with history tracking"""
    try:
        data = request.json
        new_hearing_date = data.get('new_hearing_date')
        notes = data.get('notes', '')
        
        if not new_hearing_date:
            return jsonify({'success': False, 'error': 'No hearing date provided'}), 400
        
        # Validate date format
        try:
            from datetime import datetime
            datetime.strptime(new_hearing_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        success = db.update_case_hearing_date_with_history(cino, new_hearing_date, notes)
        
        if success:
            return jsonify({
                'success': True, 
                'message': 'Hearing date updated successfully with history'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to update hearing date'}), 500
            
    except Exception as e:
        print(f"Update hearing date with history error: {e}")
        return jsonify({'success': False, 'error': f'Update failed: {str(e)}'}), 500

@app.route('/case/<cino>/update_field', methods=['POST'])
def update_case_field(cino):
    """Update any case field"""
    try:
        data = request.json
        field_name = data.get('field_name')
        field_value = data.get('field_value')
        
        if not field_name:
            return jsonify({'success': False, 'error': 'No field name provided'}), 400
        
        success = db.update_case_field(cino, field_name, field_value)
        
        if success:
            return jsonify({
                'success': True, 
                'message': f'{field_name} updated successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to update field'}), 500
            
    except Exception as e:
        print(f"Update case field error: {e}")
        return jsonify({'success': False, 'error': f'Update failed: {str(e)}'}), 500



# Add other necessary routes...
if __name__ == '__main__':
    print("Starting Law Firm Case Management System...")
    print(f"Secret key configured: {'Yes' if app.secret_key else 'No'}")
    app.run(debug=True, port=5000, host='0.0.0.0')
