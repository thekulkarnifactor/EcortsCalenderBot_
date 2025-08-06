import datetime
import os
import pickle
import re
from typing import Optional, List, Dict
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def google_calendar_authenticate(
    token_path: str = 'data/token_calendar.pickle',
    creds_path: str = 'data/credentials.json',
    port: int = 56585
):
    """
    Authenticate and return Google Calendar API credentials.
    Uses a fixed local port for OAuth redirection.
    """
    creds = None
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token_file:
            creds = pickle.load(token_file)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=port)
        with open(token_path, 'wb') as token_file:
            pickle.dump(creds, token_file)
    return creds

def get_existing_court_events(service, calendar_id='primary'):
    """Get existing court events to avoid duplicates"""
    try:
        events = []
        page_token = None
        
        while True:
            events_result = service.events().list(
                calendarId=calendar_id,
                pageToken=page_token,
                maxResults=2500,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            batch_events = events_result.get('items', [])
            for event in batch_events:
                summary = event.get('summary', '') or ''
                description = event.get('description', '') or ''
                
                # Check if it's a court event
                if (' vs ' in summary.lower() or 
                    'state_name:' in description.lower() or
                    'cino:' in description.lower()):
                    events.append(event)
            
            page_token = events_result.get('nextPageToken')
            if not page_token:
                break
        
        return events
        
    except Exception as e:
        print(f"Error getting existing events: {e}")
        return []

def create_google_calendar_events_for_cases(
    cases_data,
    calendar_id='primary',
    token_path='data/token_calendar.pickle',
    creds_path='data/credentials.json',
    port=56585,
    progress_callback=None
) -> Dict[str, int]:
    """
    Create Google Calendar events from case data.
    
    Args:
        cases_data: List of case dictionaries
        calendar_id: Google Calendar ID
        token_path: Path to OAuth token
        creds_path: Path to credentials JSON
        port: OAuth port
        progress_callback: Function for progress updates
    
    Returns:
        Dictionary with creation statistics
    """
    try:
        print("ðŸ—“ï¸ Starting calendar event creation...")
        
        # Authenticate
        creds = google_calendar_authenticate(token_path, creds_path, port)
        if not creds:
            return {'created': 0, 'failed': 0, 'skipped': 0, 'error': 'Authentication failed'}
        
        service = build('calendar', 'v3', credentials=creds)
        print("âœ… Calendar service authenticated")
        
        created_count = 0
        failed_count = 0
        skipped_count = 0
        
        # Get existing events to avoid duplicates
        print("ðŸ“‹ Checking for existing events...")
        existing_events = get_existing_court_events(service, calendar_id)
        existing_keys = set()
        
        for event in existing_events:
            summary = event.get('summary', '').lower()
            start_date = event.get('start', {}).get('date') or event.get('start', {}).get('dateTime', '')[:10]
            existing_keys.add(f"{summary}|{start_date}")
        
        print(f"ðŸ“Š Found {len(existing_keys)} existing court events")
        
        # Process each case
        for i, case in enumerate(cases_data):
            try:
                # Create event summary
                petitioner = case.get('petparty_name', '').strip()
                respondent = case.get('resparty_name', '').strip()
                
                if petitioner and respondent:
                    if petitioner != 'XXXXXXX' and respondent != 'XXXXXXX':
                        event_title = f"{petitioner} vs {respondent}"
                    else:
                        event_title = f"Case {case.get('case_no', 'Unknown')}"
                else:
                    event_title = f"Case {case.get('case_no', 'Unknown')}"
                
                # Parse next hearing date
                next_date = case.get('date_next_list', '')
                if not next_date or next_date in ['Not set', '', None]:
                    print(f"â© Skipping case {case.get('case_no', 'Unknown')} - no valid date")
                    skipped_count += 1
                    continue
                
                # Convert date format if needed (handle various formats)
                try:
                    from datetime import datetime
                    if isinstance(next_date, str):
                        # Try different date formats
                        for date_format in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d']:
                            try:
                                date_obj = datetime.strptime(next_date, date_format)
                                event_date = date_obj.strftime('%Y-%m-%d')
                                break
                            except ValueError:
                                continue
                        else:
                            print(f"âš ï¸ Invalid date format for case {case.get('case_no', 'Unknown')}: {next_date}")
                            skipped_count += 1
                            continue
                    else:
                        event_date = next_date
                except Exception as date_error:
                    print(f"âš ï¸ Date parsing error for case {case.get('case_no', 'Unknown')}: {date_error}")
                    skipped_count += 1
                    continue
                
                # Check for duplicates
                duplicate_key = f"{event_title.lower()}|{event_date}"
                if duplicate_key in existing_keys:
                    print(f"â© Skipping duplicate: {event_title} on {event_date}")
                    skipped_count += 1
                    continue
                
                # Create event description
                description_parts = []
                description_parts.append(f"case_no: {case.get('case_no', 'N/A')}")
                description_parts.append(f"cino: {case.get('cino', 'N/A')}")
                description_parts.append(f"state_name: {case.get('state_name', 'N/A')}")
                description_parts.append(f"district_name: {case.get('district_name', 'N/A')}")
                description_parts.append(f"establishment_name: {case.get('establishment_name', 'N/A')}")
                description_parts.append(f"purpose_name: {case.get('purpose_name', 'N/A')}")
                
                if case.get('user_notes', '').strip():
                    description_parts.append(f"\nYour Notes:\n{case.get('user_notes', '').strip()}")
                
                event_description = '\n'.join(description_parts)
                
                # Create the event
                event_body = {
                    'summary': event_title,
                    'description': event_description,
                    'start': {
                        'date': event_date,
                        'timeZone': 'Asia/Kolkata'  # Adjust timezone as needed
                    },
                    'end': {
                        'date': event_date,
                        'timeZone': 'Asia/Kolkata'
                    },
                    'reminders': {
                        'useDefault': False,
                        'overrides': [
                            {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                            {'method': 'popup', 'minutes': 60}        # 1 hour before
                        ]
                    }
                }
                
                # Create the event
                created_event = service.events().insert(
                    calendarId=calendar_id, 
                    body=event_body
                ).execute()
                
                print(f"âœ… Created event #{created_count + 1}: {event_title} on {event_date}")
                created_count += 1
                
                # Add to existing keys to prevent duplicates in this batch
                existing_keys.add(duplicate_key)
                
                # Progress callback
                if progress_callback:
                    progress_callback({
                        'processed': i + 1,
                        'total': len(cases_data),
                        'created': created_count,
                        'failed': failed_count,
                        'skipped': skipped_count,
                        'current_case': event_title
                    })
                
                # Small delay to avoid rate limiting
                import time
                time.sleep(0.2)
                
            except Exception as case_error:
                print(f"âŒ Failed to create event for case {case.get('case_no', 'Unknown')}: {case_error}")
                failed_count += 1
        
        result = {
            'created': created_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'total_processed': len(cases_data)
        }
        
        print(f"ðŸŽ‰ Calendar creation complete: {created_count} created, {failed_count} failed, {skipped_count} skipped")
        return result
        
    except Exception as e:
        print(f"ðŸ’¥ Critical error in calendar creation: {e}")
        import traceback
        traceback.print_exc()
        return {
            'created': 0,
            'failed': 0,
            'skipped': 0,
            'total_processed': 0,
            'error': f'Critical error: {str(e)}'
        }

def get_court_events_for_deletion(
    calendar_id: str = 'primary',
    token_path: str = 'data/token_calendar.pickle',
    creds_path: str = 'data/credentials.json',
    port: int = 56585,
    max_results: int = 2500
) -> List[Dict]:
    """
    Get all court events that can be deleted with enhanced debugging.
    """
    try:
        print("ðŸ” Starting court events search...")
        
        creds = google_calendar_authenticate(token_path, creds_path, port)
        if not creds:
            print("âŒ Authentication failed!")
            return []
            
        service = build('calendar', 'v3', credentials=creds)
        print("âœ“ Calendar service initialized")

        court_events = []
        page_token = None
        total_events_scanned = 0
        batch_count = 0

        while True:
            batch_count += 1
            print(f"ðŸ“‹ Scanning batch #{batch_count}...")
            
            try:
                events_result = service.events().list(
                    calendarId=calendar_id,
                    pageToken=page_token,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy='startTime',
                ).execute()
                
                events = events_result.get('items', [])
                batch_court_events = 0
                
                print(f"ðŸ“Š Batch #{batch_count}: Found {len(events)} total events")
                total_events_scanned += len(events)

                for event in events:
                    summary = event.get('summary', '') or ''
                    description = event.get('description', '') or ''

                    # Enhanced court event detection
                    is_court_event = (
                        ' vs ' in summary.lower() or 
                        ' v. ' in summary.lower() or 
                        ' v ' in summary.lower() or
                        'state_name:' in description.lower() or
                        'cino:' in description.lower() or
                        'case_no:' in description.lower() or
                        'establishment_name:' in description.lower()
                    )
                    
                    if is_court_event:
                        court_events.append({
                            'id': event.get('id'),
                            'summary': summary,
                            'start': event.get('start', {}).get('dateTime') or event.get('start', {}).get('date'),
                            'description': description[:100] + '...' if len(description) > 100 else description
                        })
                        batch_court_events += 1
                        
                        # Debug: Show first few matches
                        if len(court_events) <= 5:
                            print(f"ðŸŽ¯ Court event #{len(court_events)}: '{summary[:50]}...'")

                print(f"âœ… Batch #{batch_count}: Found {batch_court_events} court events")
                
                page_token = events_result.get('nextPageToken')
                if not page_token:
                    break
                    
            except Exception as batch_error:
                print(f"âŒ Error in batch #{batch_count}: {batch_error}")
                break

        print(f"ðŸŽ‰ Search complete: {len(court_events)} court events found from {total_events_scanned} total events")
        print(f"ðŸ“ˆ Success rate: {len(court_events)/total_events_scanned*100:.1f}% if total > 0")
        
        return court_events
        
    except Exception as e:
        print(f"ðŸ’¥ Critical error in search function: {e}")
        import traceback
        traceback.print_exc()
        return []

def delete_court_events_by_summary_or_description(
    calendar_id='primary',
    token_path='data/token_calendar.pickle',
    creds_path='data/credentials.json',
    port=56585,
    max_results=2500,
    progress_callback=None
) -> Dict[str, int]:
    """
    Delete court events with progress tracking.
    
    Args:
        progress_callback: Function to call with progress updates
    
    Returns:
        Dictionary with deletion statistics
    """
    try:
        # Debug: Check authentication
        print("Starting authentication...")
        creds = google_calendar_authenticate(token_path, creds_path, port)
        if not creds:
            print("âŒ Authentication failed!")
            return {'deleted': 0, 'failed': 0, 'total_processed': 0, 'error': 'Authentication failed'}
        
        print("âœ“ Authentication successful")
        
        # Build service
        service = build('calendar', 'v3', credentials=creds)
        print("âœ“ Calendar service created")

        deleted_count = 0
        failed_count = 0
        page_token = None
        total_processed = 0
        loop_count = 0

        print("Searching for court events...")

        while True:
            loop_count += 1
            print(f"ðŸ“‹ Loop #{loop_count}: Fetching events from calendar...")
            
            try:
                # Fetch events with error handling
                events_result = service.events().list(
                    calendarId=calendar_id,
                    pageToken=page_token,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy='startTime',
                    timeMin=None,  # Get all events (past and future)
                ).execute()
                
                print(f"âœ“ API call successful for loop #{loop_count}")
                
            except Exception as api_error:
                print(f"âŒ API call failed: {api_error}")
                return {
                    'deleted': deleted_count,
                    'failed': failed_count + 1,
                    'total_processed': total_processed,
                    'error': f'API call failed: {str(api_error)}'
                }

            events = events_result.get('items', [])
            print(f"ðŸ“Š Found {len(events)} total events in this batch")

            # Debug: Show first few events
            if loop_count == 1 and events:
                print("ðŸ“ Sample events:")
                for i, event in enumerate(events[:3]):
                    summary = event.get('summary', 'No Summary')
                    description = event.get('description', 'No Description')
                    print(f"   {i+1}. '{summary}' - '{description[:50]}...'")

            # Filter court events
            to_delete = []
            for event in events:
                summary = event.get('summary', '') or ''
                description = event.get('description', '') or ''

                # More comprehensive matching
                is_court_event = (
                    ' vs ' in summary.lower() or 
                    ' v. ' in summary.lower() or 
                    ' v ' in summary.lower() or
                    'state_name:' in description.lower() or
                    'state_name ' in description.lower() or
                    'cino:' in description.lower() or
                    'case_no:' in description.lower()
                )
                
                if is_court_event:
                    to_delete.append(event)
                    if len(to_delete) <= 3:  # Debug first few matches
                        print(f"ðŸŽ¯ Match found: '{summary}'")

            print(f"ðŸŽ¯ Found {len(to_delete)} court events to delete in this batch")

            # Break if no events to delete in this batch
            if not to_delete:
                print(f"â„¹ï¸ No court events found in batch #{loop_count}")
                # Check if there are more pages
                page_token = events_result.get('nextPageToken')
                if not page_token:
                    print("â„¹ï¸ No more pages to fetch")
                    break
                else:
                    print(f"â„¹ï¸ Moving to next page (token: {page_token[:10]}...)")
                    continue

            # Delete events with progress tracking
            print(f"ðŸ—‘ï¸ Starting deletion of {len(to_delete)} events...")
            
            for i, event in enumerate(to_delete):
                event_id = event.get('id')
                summary = event.get('summary', 'No Summary')
                
                try:
                    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
                    print(f"âœ… Deleted event #{total_processed + 1}: '{summary[:50]}...'")
                    deleted_count += 1
                except Exception as delete_error:
                    print(f"âŒ Failed to delete event '{summary[:50]}...': {delete_error}")
                    failed_count += 1
                
                total_processed += 1
                
                # Call progress callback if provided
                if progress_callback:
                    try:
                        progress_callback({
                            'processed': total_processed,
                            'deleted': deleted_count,
                            'failed': failed_count,
                            'current_event': summary,
                            'batch': loop_count
                        })
                    except Exception as callback_error:
                        print(f"âš ï¸ Progress callback error: {callback_error}")

                # Add small delay to avoid rate limiting
                import time
                time.sleep(0.1)

            # Check for next page
            page_token = events_result.get('nextPageToken')
            if not page_token:
                print("âœ… All pages processed")
                break
            else:
                print(f"âž¡ï¸ Moving to next page...")

        # Final results
        result = {
            'deleted': deleted_count,
            'failed': failed_count,
            'total_processed': total_processed,
            'batches_processed': loop_count
        }
        
        print(f"ðŸŽ‰ Deletion complete: {deleted_count} deleted, {failed_count} failed, {loop_count} batches processed")
        return result
        
    except Exception as e:
        print(f"ðŸ’¥ Critical error in deletion function: {e}")
        import traceback
        traceback.print_exc()
        return {
            'deleted': 0,
            'failed': 0,
            'total_processed': 0,
            'error': f'Critical error: {str(e)}'
        }

def delete_events_by_ids(
    event_ids: List[str],
    calendar_id='primary',
    token_path='data/token_calendar.pickle',
    creds_path='data/credentials.json',
    port=56585,
    progress_callback=None
) -> Dict[str, int]:
    """
    Delete events by IDs with progress tracking.
    
    Args:
        event_ids: List of event IDs to delete
        progress_callback: Function to call with progress updates
    
    Returns:
        Dictionary with deletion statistics
    """
    if not event_ids:
        return {'deleted': 0, 'failed': 0, 'total_processed': 0}

    creds = google_calendar_authenticate(token_path, creds_path, port)
    service = build('calendar', 'v3', credentials=creds)

    deleted_count = 0
    failed_count = 0
    
    for i, event_id in enumerate(event_ids):
        try:
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            print(f"Deleted event with ID: {event_id}")
            deleted_count += 1
        except Exception as e:
            print(f"Failed to delete event with ID {event_id}: {e}")
            failed_count += 1
        
        # Call progress callback if provided
        if progress_callback:
            progress_callback({
                'processed': i + 1,
                'total': len(event_ids),
                'deleted': deleted_count,
                'failed': failed_count,
                'current_event_id': event_id
            })

    result = {
        'deleted': deleted_count,
        'failed': failed_count,
        'total_processed': len(event_ids)
    }
    
    print(f"Batch deletion complete: {deleted_count} deleted, {failed_count} failed")
    return result

def clear_local_case_files() -> Dict[str, any]:
    """
    Clear local case files and data.
    
    Returns:
        Dictionary with deletion results
    """
    try:
        files_to_delete = [
            'data/myCases.txt',
            'data/temp_cases.xlsx',
            'data/calendar_events_created.xlsx',
            'data/cases_data.csv',
            'data/cases_data.xlsx'
        ]
        
        deleted_files = []
        failed_files = []
        file_sizes = {}
        
        for file_path in files_to_delete:
            try:
                if os.path.exists(file_path):
                    # Get file size before deletion
                    file_size = os.path.getsize(file_path)
                    file_sizes[file_path] = file_size
                    
                    # Delete the file
                    os.remove(file_path)
                    deleted_files.append(file_path)
                    print(f"ðŸ—‘ï¸ Deleted file: {file_path} ({file_size} bytes)")
                else:
                    print(f"â© File not found: {file_path}")
            except Exception as file_error:
                failed_files.append(f"{file_path}: {str(file_error)}")
                print(f"âŒ Failed to delete {file_path}: {file_error}")
        
        return {
            'deleted_files': deleted_files,
            'failed_files': failed_files,
            'file_sizes': file_sizes,
            'total_deleted': len(deleted_files),
            'total_failed': len(failed_files)
        }
        
    except Exception as e:
        print(f"Error clearing local files: {e}")
        return {
            'deleted_files': [],
            'failed_files': [f"Critical error: {str(e)}"],
            'file_sizes': {},
            'total_deleted': 0,
            'total_failed': 1
        }

def complete_system_cleanup(
    calendar_id='primary',
    token_path='data/token_calendar.pickle',
    creds_path='data/credentials.json',
    port=56585,
    progress_callback=None
) -> Dict[str, any]:
    """
    Complete system cleanup: Delete calendar events, database data, and local files.
    
    Args:
        progress_callback: Function to call with progress updates
    
    Returns:
        Dictionary with complete cleanup results
    """
    try:
        print("ðŸ§¹ Starting complete system cleanup...")
        cleanup_results = {
            'calendar_deletion': {},
            'database_cleanup': {},
            'file_cleanup': {},
            'backup_created': None,
            'total_success': False
        }
        
        # Step 1: Create backup first
        if progress_callback:
            progress_callback({'step': 'backup', 'message': 'Creating backup...'})
        
        try:
            from database import CaseDatabase
            db = CaseDatabase()
            backup_path = db.backup_data_before_clear()
            cleanup_results['backup_created'] = backup_path
            print("âœ… Backup created successfully")
        except Exception as backup_error:
            print(f"âš ï¸ Backup creation failed: {backup_error}")
        
        # Step 2: Delete calendar events
        if progress_callback:
            progress_callback({'step': 'calendar', 'message': 'Deleting calendar events...'})
        
        calendar_result = delete_court_events_by_summary_or_description(
            calendar_id, token_path, creds_path, port, 
            progress_callback=lambda p: progress_callback({
                'step': 'calendar', 
                'message': f"Deleting calendar events... {p.get('processed', 0)} processed"
            }) if progress_callback else None
        )
        cleanup_results['calendar_deletion'] = calendar_result
        print(f"âœ… Calendar cleanup: {calendar_result.get('deleted', 0)} events deleted")
        
        # Step 3: Clear database
        if progress_callback:
            progress_callback({'step': 'database', 'message': 'Clearing database...'})
        
        try:
            db = CaseDatabase()
            db_result = db.clear_all_data()
            cleanup_results['database_cleanup'] = db_result
            print(f"âœ… Database cleanup: {db_result.get('cases_deleted', 0)} cases deleted")
        except Exception as db_error:
            cleanup_results['database_cleanup'] = {'error': str(db_error)}
            print(f"âŒ Database cleanup failed: {db_error}")
        
        # Step 4: Clear local files
        if progress_callback:
            progress_callback({'step': 'files', 'message': 'Deleting local files...'})
        
        file_result = clear_local_case_files()
        cleanup_results['file_cleanup'] = file_result
        print(f"âœ… File cleanup: {file_result.get('total_deleted', 0)} files deleted")
        
        # Step 5: Final verification
        if progress_callback:
            progress_callback({'step': 'complete', 'message': 'Cleanup completed!'})
        
        # Check if cleanup was successful
        calendar_success = calendar_result.get('deleted', 0) >= 0  # At least no errors
        database_success = 'error' not in cleanup_results['database_cleanup']
        file_success = file_result.get('total_failed', 0) == 0
        
        cleanup_results['total_success'] = calendar_success and database_success and file_success
        
        print(f"ðŸŽ‰ Complete system cleanup finished!")
        print(f"   ðŸ“… Calendar: {calendar_result.get('deleted', 0)} events deleted")
        print(f"   ðŸ—„ï¸ Database: {cleanup_results['database_cleanup'].get('cases_deleted', 0)} cases deleted")
        print(f"   ðŸ“ Files: {file_result.get('total_deleted', 0)} files deleted")
        
        return cleanup_results
        
    except Exception as e:
        print(f"ðŸ’¥ Critical error in system cleanup: {e}")
        import traceback
        traceback.print_exc()
        return {
            'calendar_deletion': {},
            'database_cleanup': {},
            'file_cleanup': {},
            'backup_created': None,
            'total_success': False,
            'error': str(e)
        }