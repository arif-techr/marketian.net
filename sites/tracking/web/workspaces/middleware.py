from .models import Workspace, WorkspaceMember

SESSION_KEY = "workspace_id"


class CurrentWorkspaceMiddleware:
    """Sets request.workspace and request.membership for signed-in people.

    Uses the workspace picked earlier in this session if they're still a member,
    otherwise their oldest membership. Someone with no membership at all (first
    sign-in) gets a personal workspace they own.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.workspace = request.membership = None
        if request.user.is_authenticated:
            request.membership = current_membership(request)
            request.workspace = request.membership.workspace
        return self.get_response(request)


def current_membership(request):
    memberships = WorkspaceMember.objects.filter(user=request.user).select_related("workspace").order_by("created_at", "id")
    wanted = request.session.get(SESSION_KEY)
    membership = (wanted and memberships.filter(workspace_id=wanted).first()) or memberships.first()
    if membership is None:
        Workspace.personal_for(request.user)
        membership = memberships.first()
    if wanted != membership.workspace_id:
        request.session[SESSION_KEY] = membership.workspace_id
    return membership
