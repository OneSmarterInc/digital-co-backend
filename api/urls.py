from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import account_api, invite_api, views
from . import instructor_api
from . import student_api
app_name = 'api'

urlpatterns = [
    # Auth: POST username/password -> {access, refresh}; refresh -> {access}
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', views.MeView.as_view(), name='me'),
    path('me/profile/', student_api.MyProfileView.as_view(), name='me_profile'),

    # Student weekly loop
    path('student/simulations/', student_api.StudentSimulationsView.as_view(), name='student_simulations'),
    path('student/performance/', student_api.StudentPerformanceView.as_view(), name='student_performance'),
    path('run/', views.RunView.as_view(), name='run'),
    path('run/submit/', views.SubmitView.as_view(), name='run_submit'),
    path('run/advance/', views.AdvanceView.as_view(), name='run_advance'),
    path('run/debrief/', views.DebriefView.as_view(), name='run_debrief'),
    path('admin/simulations/<int:cohort_id>/deploy-faculty/', views.AdminDeployFacultyView.as_view(), name='admin_deploy_faculty'),
    path('instructor/simulations/', views.InstructorSimulationsView.as_view(), name='instructor_simulations'),
    path('instructor/people/', instructor_api.InstructorPeopleView.as_view(), name='instructor_people'),
    path('instructor/simulations/<int:cohort_id>/deploy-students/', views.InstructorDeployStudentsView.as_view(), name='instructor_deploy_students'),
    # Advisors
    path('advisors/', views.AdvisorListView.as_view(), name='advisors'),
    # War-room group chat (several advisors in one shared thread). Declared
    # before the <int:advisor_id> routes; 'group' can't match an int converter
    # anyway, but keeping them adjacent makes the advisor surface easy to read.
    path('advisors/group/', views.GroupConversationView.as_view(), name='advisor_group'),

    # Help window's ASK box -> the starved help channel (help/prompts.py).
    path('help/ask/', views.HelpAskView.as_view(), name='help_ask'),

    # Redeeming a student invitation. Unauthenticated — the token is the
    # credential and the student has no account yet.
    path('invites/<str:token>/', invite_api.InviteDetailView.as_view(), name='invite_detail'),
    path('invites/<str:token>/accept/', invite_api.InviteAcceptView.as_view(), name='invite_accept'),

    # The cohort-wide shared link the instructor console hands out. The console
    # has always generated /register/<token>; nothing served it until now.
    path('register/<str:token>/', invite_api.RegistrationDetailView.as_view(), name='registration_detail'),
    path('register/<str:token>/accept/', invite_api.RegistrationAcceptView.as_view(), name='registration_accept'),

    # Choosing a password from an emailed link (new faculty, and resets).
    path('password-reset/', account_api.PasswordResetRequestView.as_view(), name='password_reset'),
    path('set-password/<str:uidb64>/<str:token>/', account_api.SetPasswordView.as_view(), name='set_password'),
    path('advisors/group/start/', views.GroupStartView.as_view(), name='advisor_group_start'),
    path('advisors/<int:advisor_id>/', views.AdvisorConversationView.as_view(), name='advisor'),
    path('advisors/<int:advisor_id>/image/', views.AdvisorImageView.as_view(), name='advisor_image'),
    path('advisors/<int:advisor_id>/speak/', views.AdvisorSpeakView.as_view(), name='advisor_speak'),
    path('admin/people/', views.AdminPeopleView.as_view(), name='admin_people'),
    path('admin/faculty/', views.AdminFacultyView.as_view(), name='admin_faculty'),
    # Instructor
    path('instructor/queue/', views.InstructorQueueView.as_view(), name='instructor_queue'),
    path('instructor/score/<int:score_id>/', views.InstructorScoreView.as_view(), name='instructor_score'),
    path('instructor/score/<int:score_id>/feedback-draft/', views.InstructorFeedbackDraftView.as_view(), name='instructor_feedback_draft'),
    path('instructor/benchmarks/<int:cohort_id>/', views.InstructorBenchmarksView.as_view(), name='instructor_benchmarks'),
    path('instructor/benchmarks/<int:cohort_id>/reveal/<int:after_week>/', views.InstructorBenchmarkRevealView.as_view(), name='instructor_benchmark_reveal'),
    path('admin/simulations/', views.AdminSimulationsView.as_view(), name='admin_simulations'),
    path('admin/simulations/<int:cohort_id>/', views.AdminSimulationDetailView.as_view(), name='admin_simulation_detail'),
    path('admin/simulations/<int:cohort_id>/teams/', views.AdminSimulationTeamsView.as_view(), name='admin_simulation_teams'),
    # Instructor simulation management (detail, invites, enrollment, schedule, test team)
    path('instructor/simulations/<int:cohort_id>/', instructor_api.InstructorSimulationDetailView.as_view(), name='instructor_simulation_detail'),
    path('instructor/simulations/<int:cohort_id>/advance-round/', instructor_api.InstructorAdvanceRoundView.as_view(), name='instructor_advance_round'),
    path('instructor/simulations/<int:cohort_id>/invite/', instructor_api.InstructorInviteView.as_view(), name='instructor_invite'),
    path('instructor/simulations/<int:cohort_id>/invitations/', instructor_api.InstructorInvitationsView.as_view(), name='instructor_invitations'),
    path('instructor/simulations/<int:cohort_id>/invitations/<uuid:invitation_id>/resend/', instructor_api.InstructorInviteResendView.as_view(), name='instructor_invite_resend'),
    path('instructor/simulations/<int:cohort_id>/bulk-invite/', instructor_api.InstructorBulkInviteView.as_view(), name='instructor_bulk_invite'),
    path('instructor/simulations/<int:cohort_id>/bulk-invite-template/', instructor_api.InstructorBulkInviteTemplateView.as_view(), name='instructor_bulk_invite_template'),
    path('instructor/simulations/<int:cohort_id>/registration-link/', instructor_api.InstructorRegistrationLinkView.as_view(), name='instructor_registration_link'),
    path('instructor/simulations/<int:cohort_id>/rounds/<int:n>/extend/', instructor_api.InstructorExtendRoundView.as_view(), name='instructor_extend_round'),
    path('instructor/simulations/<int:cohort_id>/enrollments/<int:enrollment_id>/move/', instructor_api.InstructorMoveEnrollmentView.as_view(), name='instructor_move_enrollment'),
    path('instructor/simulations/<int:cohort_id>/enrollments/<int:enrollment_id>/paid/', instructor_api.InstructorEnrollmentPaidView.as_view(), name='instructor_enrollment_paid'),
    path('instructor/simulations/<int:cohort_id>/enrollments/paid/', instructor_api.InstructorBulkPaidView.as_view(), name='instructor_bulk_paid'),
    path('instructor/simulations/<int:cohort_id>/students/<int:enrollment_id>/', instructor_api.InstructorStudentDetailView.as_view(), name='instructor_student_detail'),
    path('instructor/simulations/<int:cohort_id>/students/<int:enrollment_id>/block/', instructor_api.InstructorStudentBlockView.as_view(), name='instructor_student_block'),
    path('instructor/simulations/<int:cohort_id>/students/<int:enrollment_id>/reset-password/', instructor_api.InstructorStudentResetPasswordView.as_view(), name='instructor_student_reset_password'),
    path('instructor/simulations/<int:cohort_id>/insights/', instructor_api.InstructorInsightsView.as_view(), name='instructor_insights'),
    path('instructor/simulations/<int:cohort_id>/instructors/', instructor_api.InstructorCoFacultyView.as_view(), name='instructor_cofaculty'),
    path('instructor/simulations/<int:cohort_id>/instructors/<int:user_id>/', instructor_api.InstructorCoFacultyDetailView.as_view(), name='instructor_cofaculty_detail'),
    path('instructor/simulations/<int:cohort_id>/firms/', instructor_api.InstructorFirmsView.as_view(), name='instructor_firms'),
    path('instructor/simulations/<int:cohort_id>/firms/<int:firm_number>/', instructor_api.InstructorFirmDetailView.as_view(), name='instructor_firm_detail'),
    path('instructor/simulations/<int:cohort_id>/firms/<int:firm_number>/insights/', instructor_api.InstructorFirmInsightsView.as_view(), name='instructor_firm_insights'),
    path('instructor/simulations/<int:cohort_id>/firms/<int:firm_number>/run/', instructor_api.InstructorMimicRunView.as_view(), name='instructor_mimic_run'),
    path('instructor/simulations/<int:cohort_id>/setup-test-team/', instructor_api.InstructorSetupTestTeamView.as_view(), name='instructor_setup_test_team'),
]