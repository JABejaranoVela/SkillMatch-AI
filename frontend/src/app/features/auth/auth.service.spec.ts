import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { of, throwError } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { sanitizeReturnUrl } from './auth.service';
import { AuthService } from './auth.service';

describe('sanitizeReturnUrl', () => {
  it('keeps an internal route with its query string', () => {
    expect(sanitizeReturnUrl('/jobs?remote=true')).toBe('/jobs?remote=true');
  });

  it('rejects external and protocol-relative URLs', () => {
    expect(sanitizeReturnUrl('https://example.com')).toBe('/resumes');
    expect(sanitizeReturnUrl('//example.com/jobs')).toBe('/resumes');
  });

  it('does not redirect back to login', () => {
    expect(sanitizeReturnUrl('/login?returnUrl=/jobs')).toBe('/resumes');
  });
});

describe('AuthService email verification', () => {
  let http: jasmine.SpyObj<HttpClient>;
  let service: AuthService;

  beforeEach(() => {
    http = jasmine.createSpyObj<HttpClient>('HttpClient', ['get', 'post', 'patch']);
    http.get.and.returnValue(throwError(() => ({ status: 401 })));

    service = new AuthService(
      http,
      { baseUrl: '/api/v1' } as ApiService,
      jasmine.createSpyObj<Router>('Router', ['navigate', 'navigateByUrl'])
    );
  });

  it('does not refresh or replace the active session after verifying email', () => {
    const sessionRequestsBeforeVerify = http.get.calls.count();
    http.post.and.returnValue(of({ message: 'Correo verificado correctamente' }));

    service.verifyEmail('email-token').subscribe();

    expect(http.post).toHaveBeenCalledWith('/api/v1/auth/verify-email', {
      token: 'email-token'
    });
    expect(http.get.calls.count()).toBe(sessionRequestsBeforeVerify);
  });

  it('clears local session state even when logout has no active backend session', () => {
    http.post.and.returnValue(throwError(() => ({ status: 401 })));

    service.logoutCurrentSession().subscribe();

    expect(service.isAuthenticated).toBeFalse();
  });
});
