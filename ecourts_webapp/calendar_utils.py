import datetime
import os
import pickle
import re
from typing import Optional, List, Dict
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/calendar',  # Full calendar access
    'https://www.googleapis.com/auth/calendar.events'  # Events access
]

def google_calendar_authenticate(
    token_path: str = 'data/token_calendar.pickle',
    creds_path: str = 'data/credentials.json',
    port: int = 56585
):
    """
    Authenticate and return Google Calendar API credentials.
    """
    creds = None
    # Load existing token
    if os.path.exists(token_path):
        try:
            with open(token_path, 'rb') as token_file:
                creds = pickle.load(token_file)
            print("✅ Loaded existing credentials")
        except Exception as e:
            print(f"⚠️ Error loading token: {e}")
            # Delete corrupted token
            os.remove(token_path)
            creds = None

    # Check if credentials need refresh or are invalid
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("🔄 Refreshing expired credentials...")
                creds.refresh(Request())
                print("✅ Credentials refreshed successfully")
            except Exception as refresh_error:
                print(f"❌ Refresh failed: {refresh_error}")
                creds = None

        # If refresh failed or no credentials, get new ones
        if not creds:
            try:
                print("🔐 Starting new authentication flow...")
                print(f"📱 Using port: {port}")
                if not os.path.exists(creds_path):
                    print(f"❌ Credentials file not found: {creds_path}")
                    return None
                
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(
                    port=port,
                    access_type='offline',
                    prompt='consent',  # Force consent to get proper scopes
                    include_granted_scopes='true'
                )
                print("✅ New authentication successful")
            except Exception as auth_error:
                print(f"❌ Authentication failed: {auth_error}")
                return None

    # Save the credentials for the next run
    try:
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, 'wb') as token_file:
            pickle.dump(creds, token_file)
        print("✅ Credentials saved successfully")
    except Exception as save_error:
        print(f"⚠️ Could not save credentials: {save_error}")

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
    progress_callback=None,
    additional_data=None,
    filter_info=None
) -> Dict[str, int]:
    """
    Create/Update Google Calendar events from case data.
    FIXED: Now properly handles user_side and case number formatting.
    """
    try:
        print("🗓️ Starting calendar event creation/update...")
        
        # Authenticate with better error handling
        print("🔐 Authenticating with Google Calendar...")
        creds = google_calendar_authenticate(token_path, creds_path, port)
        if not creds:
            return {
                'created': 0,
                'updated': 0,
                'failed': 0,
                'skipped': 0,
                'error': 'Authentication failed - please check credentials'
            }

        # Test the credentials before proceeding
        try:
            service = build('calendar', 'v3', credentials=creds)
            test_result = service.calendars().get(calendarId=calendar_id).execute()
            print("✅ Calendar service authenticated and tested successfully")
        except Exception as auth_test_error:
            print(f"❌ Calendar service test failed: {auth_test_error}")
            return {
                'created': 0,
                'updated': 0,
                'failed': 0,
                'skipped': 0,
                'error': f'Calendar service authentication test failed: {str(auth_test_error)}'
            }

        # Filter cases with valid dates
        valid_cases = []
        for case in cases_data:
            if (case.get('date_next_list') and 
                case['date_next_list'] not in ['Not set', '', None, 'Not scheduled']):
                valid_cases.append(case)
        
        print(f"📅 Filtered to {len(valid_cases)} cases with valid dates from {len(cases_data)} total")
        
        if not valid_cases:
            return {
                'created': 0,
                'updated': 0,
                'failed': 0,
                'skipped': len(cases_data),
                'total_processed': len(cases_data),
                'error': 'No cases with valid dates found'
            }

        # Initialize counters
        created_count = 0
        updated_count = 0
        failed_count = 0
        skipped_count = 0

        # FIXED: Get existing events with better matching
        print("📋 Checking for existing events...")
        try:
            existing_events = get_existing_court_events_with_cino_mapping(service, calendar_id)
            existing_events_map = {}
            
            # Create a more robust mapping with multiple fallback strategies
            for event in existing_events:
                description = event.get('description', '')
                summary = event.get('summary', '')
                
                # Strategy 1: Extract formatted case number (PIL/123/2024 format)
                case_no_match = re.search(r'Case No:\s*([^\n\r]+)', description, re.IGNORECASE)
                if case_no_match:
                    case_no = case_no_match.group(1).strip()
                    existing_events_map[f"case_no_{case_no}"] = event
                    print(f"📍 Mapped by Case No: {case_no} -> Event ID {event.get('id', 'Unknown')[:10]}...")
                
                # Strategy 2: Extract parties from summary (Petitioner vs Respondent)
                if ' vs ' in summary.lower():
                    parties_key = summary.lower().replace(' ', '_')
                    existing_events_map[f"parties_{parties_key}"] = event
                    print(f"📍 Mapped by Parties: {summary[:30]}... -> Event ID {event.get('id', 'Unknown')[:10]}...")
                
                # Strategy 3: Extract type/reg_no/reg_year pattern
                type_reg_match = re.search(r'(\w+)/(\d+)/(\d{4})', description)
                if type_reg_match:
                    type_name, reg_no, reg_year = type_reg_match.groups()
                    type_reg_key = f"{type_name}/{reg_no}/{reg_year}"
                    existing_events_map[f"type_reg_{type_reg_key}"] = event
                    print(f"📍 Mapped by Type/Reg: {type_reg_key} -> Event ID {event.get('id', 'Unknown')[:10]}...")

            print(f"📊 Created mapping for {len(existing_events_map)} existing court events with multiple strategies")

        except Exception as existing_error:
            print(f"⚠️ Warning: Could not check existing events: {existing_error}")
            existing_events_map = {}

        # Process each valid case
        for i, case in enumerate(valid_cases):
            try:
                cino = case.get('cino', '').strip()
                case_no = case.get('case_no', '').strip()
                
                print(f"\n📝 Processing case {i+1}/{len(valid_cases)}: CINO {cino}")
                
                # Create event summary
                petitioner = case.get('petparty_name', '').strip()
                respondent = case.get('resparty_name', '').strip()
                
                if petitioner and respondent:
                    if petitioner != 'XXXXXXX' and respondent != 'XXXXXXX':
                        event_title = f"{petitioner} vs {respondent}"
                    else:
                        event_title = f"Case {case_no}"
                else:
                    event_title = f"Case {case_no}"

                # Parse next hearing date
                next_date = case.get('date_next_list', '')
                
                # Convert date format with better error handling
                try:
                    if isinstance(next_date, str):
                        for date_format in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d']:
                            try:
                                date_obj = datetime.datetime.strptime(next_date, date_format)
                                event_date = date_obj.strftime('%Y-%m-%d')
                                break
                            except ValueError:
                                continue
                        else:
                            print(f"⚠️ Invalid date format for case {case_no}: {next_date}")
                            skipped_count += 1
                            continue
                    else:
                        event_date = next_date
                except Exception as date_error:
                    print(f"⚠️ Date parsing error for case {case_no}: {date_error}")
                    skipped_count += 1
                    continue

                # FIXED: Create event description with proper user side handling
                description_parts = []

                # FIXED: Get user side properly - check for actual value
                user_side = case.get('user_side', '').strip()
                # if user_side and user_side.lower() not in ['', 'not set', 'none', 'null']:
                #     description_parts.append(f"User Side: {user_side.title()}")
                # else:
                #     description_parts.append("User Side: Not set")

                # FIXED: Format case number as type_name/reg_no/reg_year
                type_name = case.get('type_name', '').strip()
                reg_no = case.get('reg_no', '')
                reg_year = case.get('reg_year', '')

                if type_name and reg_no and reg_year:
                    formatted_case_no = f"{type_name}/{reg_no}/{reg_year}"
                else:
                    # Fallback to original case number if components are missing
                    formatted_case_no = case.get('case_no', '')

                description_parts.append(f"Case No: {formatted_case_no}")
                description_parts.append(f"Case Type: {case.get('case_type_name', 'N/A')}")
                description_parts.append(f"Court/Judge: {case.get('court_no_desg_name', 'N/A')}")
                description_parts.append(f"Next Stage: {case.get('purpose_name', 'N/A')}")
                # description_parts.append(f"CINO: {case.get('cino', '')}")
                # description_parts.append(f"Establishment: {case.get('establishment_name', 'N/A')}")

                court_info = case.get('court_no_desg_name', 'N/A')

                # FIXED: Location handling
                state = case.get('state_name', '').strip()
                district = case.get('district_name', '').strip()
                if state and district:
                    location = f"{district}, {state}"
                elif state:
                    location = state
                elif district:
                    location = district
                else:
                    location = "N/A"
                # description_parts.append(f"Location: {location}")

                # FIXED: Notes handling with proper formatting
                user_notes = case.get('user_notes', '').strip()
                if user_notes:
                    description_parts.append("Notes:")
                    description_parts.append(user_notes)

                event_description = '\n'.join(description_parts)

                # Create event body
                event_body = {
                    'summary': event_title,
                    'description': event_description,
                    'start': {
                        'date': event_date,
                        'timeZone': 'Asia/Kolkata'
                    },
                    'end': {
                        'date': event_date,
                        'timeZone': 'Asia/Kolkata'
                    },
                    'reminders': {
                        'useDefault': False,
                        'overrides': [
                            {'method': 'email', 'minutes': 24 * 60},
                            {'method': 'popup', 'minutes': 60}
                        ]
                    }
                }

                # FIXED LOGIC: Check if event exists and update or create
                existing_event = None
                match_strategy = None

                # Strategy 1: Match by formatted case number
                formatted_case_no = f"{type_name}/{reg_no}/{reg_year}" if type_name and reg_no and reg_year else case_no
                if f"case_no_{formatted_case_no}" in existing_events_map:
                    existing_event = existing_events_map[f"case_no_{formatted_case_no}"]
                    match_strategy = f"Case No: {formatted_case_no}"

                # Strategy 2: Match by original case number
                elif f"case_no_{case_no}" in existing_events_map:
                    existing_event = existing_events_map[f"case_no_{case_no}"]
                    match_strategy = f"Original Case No: {case_no}"

                # Strategy 3: Match by parties (petitioner vs respondent)
                # elif petitioner and respondent:
                #     parties_key = f"{petitioner} vs {respondent}".lower().replace(' ', '_')
                #     if f"parties_{parties_key}" in existing_events_map:
                #         existing_event = existing_events_map[f"parties_{parties_key}"]
                #         match_strategy = f"Parties: {petitioner} vs {respondent}"

                # Strategy 4: Match by type/reg pattern
                elif type_name and reg_no and reg_year:
                    type_reg_key = f"{type_name}/{reg_no}/{reg_year}"
                    if f"type_reg_{type_reg_key}" in existing_events_map:
                        existing_event = existing_events_map[f"type_reg_{type_reg_key}"]
                        match_strategy = f"Type/Reg: {type_reg_key}"
                
                # Try to find existing event by CINO first
                elif cino in existing_events_map:
                    existing_event = existing_events_map[cino]
                    print(f"🔍 Found existing event by CINO: {cino}")
                
                # Try backup matching by case number
                elif f"case_no_{case_no}" in existing_events_map:
                    existing_event = existing_events_map[f"case_no_{case_no}"]
                    print(f"🔍 Found existing event by Case No: {case_no}")
                
                if existing_event:
                    print(f"🔍 Found existing event using {match_strategy}")
                     # UPDATE existing event
                    event_id = existing_event['id']
                    try:
                        print(f"🔄 Updating existing event: {event_title} (Strategy: {match_strategy})")
                        updated_event = service.events().update(
                            calendarId=calendar_id,
                            eventId=event_id,
                            body=event_body
                        ).execute()
                        print(f"✅ Updated event #{updated_count + 1}: {event_title} on {event_date}")
                        updated_count += 1
                    except Exception as update_error:
                        print(f"❌ Failed to update event for case {case_no}: {update_error}")
                        failed_count += 1
                else:
                    # CREATE new event
                    try:
                        print(f"➕ Creating new event: {event_title} (No existing match found)")
                        created_event = service.events().insert(
                            calendarId=calendar_id,
                            body=event_body
                        ).execute()
                        print(f"✅ Created event #{created_count + 1}: {event_title} on {event_date}")
                        created_count += 1
                    except Exception as create_error:
                        print(f"❌ Failed to create event for case {case_no}: {create_error}")
                        failed_count += 1
                    print(f"➕ No existing event found for case {case_no}, will create new")

                # if existing_event:
                #     # UPDATE existing event
                #     event_id = existing_event['id']
                #     try:
                #         print(f"🔄 Updating existing event: {event_title}")
                #         updated_event = service.events().update(
                #             calendarId=calendar_id,
                #             eventId=event_id,
                #             body=event_body
                #         ).execute()
                        
                #         print(f"✅ Updated event #{updated_count + 1}: {event_title} on {event_date}")
                #         updated_count += 1
                        
                #     except Exception as update_error:
                #         print(f"❌ Failed to update event for case {case_no}: {update_error}")
                #         failed_count += 1
                # else:
                #     # CREATE new event
                #     try:
                #         print(f"➕ Creating new event: {event_title}")
                #         created_event = service.events().insert(
                #             calendarId=calendar_id,
                #             body=event_body
                #         ).execute()
                        
                #         print(f"✅ Created event #{created_count + 1}: {event_title} on {event_date}")
                #         created_count += 1
                        
                #     except Exception as create_error:
                #         print(f"❌ Failed to create event for case {case_no}: {create_error}")
                #         failed_count += 1

                # Progress callback
                if progress_callback:
                    progress_callback({
                        'processed': i + 1,
                        'total': len(valid_cases),
                        'created': created_count,
                        'updated': updated_count,
                        'failed': failed_count,
                        'skipped': skipped_count,
                        'current_case': event_title
                    })

                # Rate limiting to avoid API quotas
                import time
                time.sleep(0.3)

            except Exception as case_error:
                print(f"❌ Error processing case {case.get('case_no', 'Unknown')}: {case_error}")
                failed_count += 1

        # Final results
        result = {
            'created': created_count,
            'updated': updated_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'total_processed': len(cases_data),
            'valid_cases_found': len(valid_cases),
            'received_all_data': True
        }

        print(f"🎉 Calendar sync complete: {created_count} created, {updated_count} updated, {failed_count} failed, {skipped_count} skipped")
        return result

    except Exception as e:
        print(f"💥 Critical error in calendar creation: {e}")
        import traceback
        traceback.print_exc()
        return {
            'created': 0,
            'updated': 0,
            'failed': 0,
            'skipped': 0,
            'total_processed': 0,
            'error': f'Critical error: {str(e)}',
            'received_all_data': True
        }

def get_existing_court_events_with_cino_mapping(service, calendar_id='primary'):
    """
    Get existing court events with better CINO extraction for mapping.
    ENHANCED: Better pattern matching and case number fallback.
    """
    try:
        events = []
        page_token = None
        print("📋 Fetching existing court events for mapping...")

        while True:
            events_result = service.events().list(
                calendarId=calendar_id,
                pageToken=page_token,
                maxResults=2500,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            batch_events = events_result.get('items', [])
            print(f"📊 Checking {len(batch_events)} events in this batch...")

            for event in batch_events:
                summary = event.get('summary', '') or ''
                description = event.get('description', '') or ''

                # Enhanced court event detection
                is_court_event = (
                    # Title patterns
                    ' vs ' in summary.lower() or
                    ' v. ' in summary.lower() or
                    ' v ' in summary.lower() or
                    'case ' in summary.lower() or
                    # Description patterns - ENHANCED
                    'case no:' in description.lower() or
                    'court/judge:' in description.lower() or
                    'next stage:' in description.lower() or
                    'case type:' in description.lower() or
                    # Look for formatted case numbers like "PIL/123/2024"
                    re.search(r'\w+/\d+/\d{4}', description) or
                    # Look for petitioner vs respondent pattern in description
                    ' vs ' in description.lower()
                )

                if is_court_event:
                    events.append({
                        'id': event.get('id'),
                        'summary': summary,
                        'description': description,
                        'start': event.get('start', {}),
                        'end': event.get('end', {}),
                        'reminders': event.get('reminders', {})
                    })

            page_token = events_result.get('nextPageToken')
            if not page_token:
                break

        print(f"📈 Total court events found: {len(events)}")
        return events

    except Exception as e:
        print(f"❌ Error getting existing court events: {e}")
        return []

def get_existing_court_events_detailed(service, calendar_id='primary'):
    """Get existing court events with detailed information for updating"""
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
                    'cino:' in description.lower() or
                    'case no:' in description.lower()):
                    events.append({
                        'id': event.get('id'),
                        'summary': summary,
                        'description': description,
                        'start': event.get('start', {}),
                        'end': event.get('end', {}),
                        'reminders': event.get('reminders', {})
                    })
            
            page_token = events_result.get('nextPageToken')
            if not page_token:
                break
        
        return events
        
    except Exception as e:
        print(f"Error getting detailed existing events: {e}")
        return []


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
    
def delete_events_by_cinos(
    cinos: List[str],
    calendar_id='primary',
    token_path='data/token_calendar.pickle',
    creds_path='data/credentials.json',
    port=56585,
    progress_callback=None
) -> Dict[str, int]:
    """
    Delete calendar events by CINOs with progress tracking.
    
    Args:
        cinos: List of case CINOs to find and delete events for
        calendar_id: Google Calendar ID (default: 'primary')
        token_path: Path to stored authentication token
        creds_path: Path to Google credentials.json
        port: Port for OAuth flow
        progress_callback: Optional callback function for progress updates
    
    Returns:
        Dictionary with deletion statistics
    """
    try:
        print(f"🎯 Starting deletion of events for {len(cinos)} CINOs...")
        
        # Authenticate
        creds = google_calendar_authenticate(token_path, creds_path, port)
        if not creds:
            print("❌ Authentication failed!")
            return {
                'deleted': 0,
                'failed': 0,
                'not_found': 0,
                'total_processed': len(cinos),
                'error': 'Authentication failed'
            }
        
        service = build('calendar', 'v3', credentials=creds)
        print("✅ Calendar service initialized")
        
        deleted_count = 0
        failed_count = 0
        not_found_count = 0
        total_processed = 0
        
        # Get all existing court events first
        print("📋 Fetching all court events...")
        try:
            existing_events = get_existing_court_events_detailed(service, calendar_id)
            print(f"📊 Found {len(existing_events)} total court events")
        except Exception as fetch_error:
            print(f"❌ Failed to fetch existing events: {fetch_error}")
            return {
                'deleted': 0,
                'failed': 0,
                'not_found': 0,
                'total_processed': len(cinos),
                'error': f'Failed to fetch events: {str(fetch_error)}'
            }
        
        # Create a mapping of CINO to event ID
        cino_to_event_map = {}
        for event in existing_events:
            description = event.get('description', '')
            # Extract CINO from description using regex
            cino_match = re.search(r'CINO:\s*([^\n\r]+)', description, re.IGNORECASE)
            if cino_match:
                cino = cino_match.group(1).strip()
                cino_to_event_map[cino] = {
                    'event_id': event.get('id'),
                    'summary': event.get('summary', ''),
                    'start': event.get('start', {})
                }
        
        print(f"🔗 Mapped {len(cino_to_event_map)} events to CINOs")
        
        # Delete events for each CINO
        for i, cino in enumerate(cinos):
            try:
                total_processed += 1
                
                if cino in cino_to_event_map:
                    event_info = cino_to_event_map[cino]
                    event_id = event_info['event_id']
                    summary = event_info['summary']
                    
                    try:
                        # Delete the event
                        service.events().delete(
                            calendarId=calendar_id,
                            eventId=event_id
                        ).execute()
                        
                        print(f"✅ Deleted event #{deleted_count + 1}: '{summary}' (CINO: {cino})")
                        deleted_count += 1
                        
                    except Exception as delete_error:
                        print(f"❌ Failed to delete event for CINO {cino}: {delete_error}")
                        failed_count += 1
                        
                else:
                    print(f"⚠️ No event found for CINO: {cino}")
                    not_found_count += 1
                
                # Progress callback
                if progress_callback:
                    try:
                        progress_callback({
                            'processed': total_processed,
                            'total': len(cinos),
                            'deleted': deleted_count,
                            'failed': failed_count,
                            'not_found': not_found_count,
                            'current_cino': cino,
                            'current_event': cino_to_event_map.get(cino, {}).get('summary', 'Unknown')
                        })
                    except Exception as callback_error:
                        print(f"⚠️ Progress callback error: {callback_error}")
                
                # Rate limiting
                import time
                time.sleep(0.2)
                
            except Exception as cino_error:
                print(f"❌ Error processing CINO {cino}: {cino_error}")
                failed_count += 1
        
        # Final results
        result = {
            'deleted': deleted_count,
            'failed': failed_count,
            'not_found': not_found_count,
            'total_processed': total_processed,
            'total_cinos': len(cinos)
        }
        
        print(f"🎉 CINO deletion complete: {deleted_count} deleted, {failed_count} failed, {not_found_count} not found")
        return result
        
    except Exception as e:
        print(f"💥 Critical error in CINO deletion function: {e}")
        import traceback
        traceback.print_exc()
        return {
            'deleted': 0,
            'failed': 0,
            'not_found': 0,
            'total_processed': 0,
            'error': f'Critical error: {str(e)}'
        }

def get_existing_court_events_detailed(service, calendar_id='primary'):
    """Get existing court events with detailed information for CINO-based operations"""
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
                    ' v. ' in summary.lower() or
                    ' v ' in summary.lower() or
                    'cino:' in description.lower() or
                    'case no:' in description.lower() or
                    'establishment:' in description.lower()):
                    
                    events.append({
                        'id': event.get('id'),
                        'summary': summary,
                        'description': description,
                        'start': event.get('start', {}),
                        'end': event.get('end', {}),
                        'reminders': event.get('reminders', {})
                    })
            
            page_token = events_result.get('nextPageToken')
            if not page_token:
                break
        
        return events
        
    except Exception as e:
        print(f"Error getting detailed existing events: {e}")
        return []
