## Introduction
You are an expert frontend designer and developer.
You are tasked to build a resume analysis webapp for job seekers.
There should be two types of users viz.
- Candidate
- Admin.

### Application Requirement


#### Candidates

##### Feature: Application Landing Page
- Landing page with impactful visuals, (suggest a catchy name for this application and description)

##### Feature: User Resistration
- User registration and login (including OAuth providers Google and LinkedIn)

##### Feature: Post login home page 
- Landing screen where they will see their dashboard.

##### Feature: User Dashboard
- Dashboard shows number of resumes created, number of analyses ran. 

- Dashboard also allows users to create and upload resumes (drag/drop and file selection - only .pdf, .doc and .docx)

- A list of available resumes in tabular format with resume name, upload date, analysis date, analysis status (unanalyzed, completed, in progress, failed) and actions (analyze, edit, delete)

##### Feature: Resume Creation and Editing

- When user selects Create resume - user is presented with a form that follows the json-resume-schema as described on this link -> https://raw.githubusercontent.com/jsonresume/resume-schema/refs/heads/master/schema.json . All the fields should be editable and use appropriate UI control for the type of field.

-  After saving the resume, user see well formatted resume content. Each field when hovered over shows a pencil icon. When this icon is clicked only that field is enabled for in-place editing.

- When user submits the resume, the resume is saved in the database. When saving is complete, user then has a button to analyze the resume,

- When user selects to edit the resume from resume list, the same resume view is shown. with all the in-place editing, saving and analysis functionality as on resume creation screen.

- The editable form should have **ALL** the fields editable including dates. If some field from the json-resume-schema is missing, it should have an editable placeholder. When the form is submitted and the placeholder field holds not value, it should be ignored. In no circumstances the placeholder should be stored in the database.

##### Feature: Upload Resume

- When user uploads the resume, the backend server will attempt to convert the resume to the `json-resume-schema` using AI backend.
- While AI processes the resume, the user should see progress indicator - clearly informing user that the resume is being processed.
- Once the processing is done, the user should be taken to the resume edit screen.
- The backend would return the processd resume in json-resume-schema format, as well as original resume text.
- On the resume edit screen:
  - the resume should be populated with processed resume field (which followg json-resume-schema structure) - show this on left half of the screen.
  - Extracted original resume text - show this on the right half of the screen.
  - This is where users can manually correct the processed resume if there any any errors or the AI parsing omitted any sections.
  - There should be appropriate validations on all fields in the editable form.
  - Once user is satisfied with the transformed resume, user can save the resume.
  - Once transformed resume is saved, allow user to start resume analysis.

##### Feature: Analysis
- When user clicks the "Analyze Resume" button, user is taken to the analysis screen.
- User can only go to this screen if the user has resume.
- On this screen, Provide a text area for the user to paste target job description and analysis name.
- The resume details/edit screen from where user navigated to this screen, the same resume should be used to analyze the job description against. In other words, that resume should be selected.
- User has two buttons:
  - Clear button (wipes out values in job description and analysis name fields)
  - Start Analysis button which triggers the analysis for the job description and the given resume.

##### Feature: Analysis Progress
- Backend server performs this AI based analysis and may take a while (approx 30-45 seconds) for the processing to finish.
- Analysis has 3 steps:
  - Comparing resume and job description.
  - Generating Suggestions.
  - Preparing Interview Questions.
- Clearly show these steps and their progress status to the user Pending, in progress, completed with appropriate color coding.
- There shoudl be a notification in the top navigation bar indicating analysis is in progress. If the user navigates to some other part of the application, the notification stays until analysis is finished. Clickin on the notification takes the user back to the analysis progress screen.
- When analysis is complete, provide a visual cue to the user indicating completion of the analysis. This Notification should be cleared when the user either visits the analysis details page for that analysis or clears it manually.

##### Feature: Analysis results
- On analysis success, the backend server returns the analysis results 
  - Analysis Result: overall resume score, ATS compatibility score, strong points, weak points, matching skills, skill gaps.
  - Improvement Suggestions: ATS improvement suggestion, skills that need emphasis, things that can be worded better, skills to be added to the resume and project score. Grouped by each relevant field.
  - Interview Questions: List of probably interview questions and answers.
- Show all this information in a well organised manner.
- Bellow that, show a button "Apply suggestions to the resune"
- When user clicks this button, take the user to the resume modifications page.

##### Feature: Apply Suggestions to the Resume
- Show current resume on the left
- Show suggestions on the right.
- Users can apply individual suggestion to the individual fields.
- Save option.
- Download dropdown - Show pdf and docx options.


#### Admin

- Use the same login screen. 
- Do not create separate Admin registration flow.
- Whether the user is admin or not is dictated by the bacckend using RBAC.

##### Top Navigation Bar
- A navigation bar at the top allowin admin to visit various features in the admin section.

##### Feature: Dashboard page
- Show an admin dashboard summarizing how many users have registered, how many resumes exists (created and upload combined), how many analyses were run.

##### Feature: User List
- Admin can search users by id, email or name.
- Show existing users list in tabular format - show User Full Name, email address, registration date, last active date, registration date, number of resumes, number of analyses performed and actions - Details and deactivate.

##### Feature: User details
- Admin can edit the user details like name and email address.
- Admin can reset user's password.
- Admin can view List of resumes - resume name, number of analyses performed.
- Admin should not be able to view user's resumes and analyses.
- Admin can delete resumes and associated analyses.

##### Settings
- List of existing AI models - model name, provider API key (masked)
- Ability to add a new model and API keys

### Instructions
- The application should be fully responsive supporting all the standard screen sizes from phones, tablets, both orientations, mid, large and xl screens.
- Use both light and dark themes.
- Look and feel of the components should like those on https://www.pinecone.io/
- Application should look beautiful, professional, crisp and modern
- Application should follow all the standards that make the UI score the highest on web vitals.
- Application should be fully accessible.