from mama_cas.compat import is_authenticated as mama_is_authenticated
from mama_cas.models import ProxyGrantingTicket as MamaProxyGrantingTicket
from mama_cas.models import ProxyTicket as MamaProxyTicket
from mama_cas.models import ServiceTicket as MamaServiceTicket
from mama_cas.utils import redirect as mama_redirect
from mama_cas.utils import to_bool as mama_to_bool
from mama_cas.views import LoginView as MamaLoginView
from mama_cas.views import LogoutView as MamaLogoutView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth import logout
from django.http import HttpResponseRedirect

from idgo_admin.forms.account import SignInForm

decorators = [csrf_exempt, login_required(login_url=settings.LOGIN_URL)]

@method_decorator(decorators[0], name='dispatch')
class SignIn(MamaLoginView):

    template_name = 'idgo_admin/signin.html'
    form_class = SignInForm

    def get(self, request, *args, **kwargs):
        service = request.GET.get('service')
        gateway = mama_to_bool(request.GET.get('gateway'))
        if gateway and service:
            if mama_is_authenticated(request.user):
                st = MamaServiceTicket.objects.create_ticket(
                    service=service, user=request.user)
                if self.warn_user():
                    return mama_redirect('cas_warn', params={'service': service, 'ticket': st.ticket})
                return mama_redirect(service, params={'ticket': st.ticket})
            else:
                return mama_redirect(service)
        elif mama_is_authenticated(request.user):
            if service:
                st = MamaServiceTicket.objects.create_ticket(service=service, user=request.user)
                if self.warn_user():
                    return mama_redirect('cas_warn', params={'service': service, 'ticket': st.ticket})
                return mama_redirect(service, params={'ticket': st.ticket})
        return super(MamaLoginView, self).get(request, *args, **kwargs)

    def form_valid(self, form):
        login(self.request, form.user)

        if form.cleaned_data.get('warn'):
            self.request.session['warn'] = True

        service = self.request.GET.get('service')
        if service:
            st = MamaServiceTicket.objects.create_ticket(
                service=service, user=self.request.user, primary=True)
            return mama_redirect(service, params={'ticket': st.ticket})

        nxt_pth = self.request.GET.get('next', None)
        if nxt_pth:
            return HttpResponseRedirect(nxt_pth)

        return mama_redirect('idgo_admin:list_my_datasets')


def logout_user(request):
    if mama_is_authenticated(request.user):
        MamaServiceTicket.objects.consume_tickets(request.user)
        MamaProxyTicket.objects.consume_tickets(request.user)
        MamaProxyGrantingTicket.objects.consume_tickets(request.user)
        MamaServiceTicket.objects.request_sign_out(request.user)
        logout(request)

class SignOut(MamaLogoutView):

    def get(self, request, *args, **kwargs):

        service = request.GET.get('service')
        if not service:
            service = request.GET.get('url')
        follow_url = getattr(settings, 'MAMA_CAS_FOLLOW_LOGOUT_URL', True)
        logout_user(request)
        if service and follow_url:
            return mama_redirect(service)
        return mama_redirect('server_cas:signIn')
