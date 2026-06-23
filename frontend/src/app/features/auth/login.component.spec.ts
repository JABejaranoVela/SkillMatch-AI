import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { AuthService, AuthUser } from './auth.service';
import { LoginComponent } from './login.component';

describe('LoginComponent', () => {
  let fixture: ComponentFixture<LoginComponent>;
  let component: LoginComponent;
  let authService: jasmine.SpyObj<AuthService>;
  let router: Router;

  const activeUser: AuthUser = {
    id: 1,
    email: 'user@example.com',
    full_name: 'Test User',
    role: 'user',
    status: 'active',
    email_verified_at: '2026-06-11T10:00:00Z'
  };

  async function createComponent(query: Record<string, string> = {}): Promise<void> {
    authService = jasmine.createSpyObj<AuthService>(
      'AuthService',
      ['login', 'safeReturnUrl']
    );
    authService.safeReturnUrl.and.callFake((value) => value || '/resumes');
    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: authService },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { queryParamMap: convertToParamMap(query) }
          }
        }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(LoginComponent);
    component = fixture.componentInstance;
    router = TestBed.inject(Router);
    fixture.detectChanges();
  }

  afterEach(() => TestBed.resetTestingModule());

  it('shows a safe generic error when login fails', async () => {
    await createComponent();
    authService.login.and.returnValue(throwError(() => ({ status: 401 })));
    component.form.setValue({
      email: 'user@example.com',
      password: 'incorrect-password'
    });

    component.submit();

    expect(component.errorMessage).toContain('No hemos podido iniciar sesión');
  });

  it('redirects a pending user to email verification', async () => {
    await createComponent({ returnUrl: '/jobs' });
    const navigateSpy = spyOn(router, 'navigateByUrl');
    authService.login.and.returnValue(of({
      ...activeUser,
      status: 'pending',
      email_verified_at: null
    }));
    component.form.setValue({
      email: 'user@example.com',
      password: 'valid-password'
    });

    component.submit();

    expect(navigateSpy).toHaveBeenCalledWith('/verify-email-sent');
  });

  it('uses the validated return URL after login', async () => {
    await createComponent({ returnUrl: '/jobs?remote=true' });
    const navigateSpy = spyOn(router, 'navigateByUrl');
    authService.safeReturnUrl.and.returnValue('/jobs?remote=true');
    authService.login.and.returnValue(of(activeUser));
    component.form.setValue({
      email: 'user@example.com',
      password: 'valid-password'
    });

    component.submit();

    expect(authService.safeReturnUrl).toHaveBeenCalledWith('/jobs?remote=true');
    expect(navigateSpy).toHaveBeenCalledWith('/jobs?remote=true');
  });

  it('shows a verified email message from the login reason', async () => {
    await createComponent({ reason: 'verified' });

    expect(component.accountMessage).toBe(
      'Correo verificado. Ahora puedes iniciar sesión.'
    );
  });
});
