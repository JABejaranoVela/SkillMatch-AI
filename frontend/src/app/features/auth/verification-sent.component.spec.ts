import { HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';

import { AuthService, AuthUser } from './auth.service';
import { VerificationSentComponent } from './verification-sent.component';

describe('VerificationSentComponent', () => {
  let fixture: ComponentFixture<VerificationSentComponent>;
  let component: VerificationSentComponent;
  let authService: jasmine.SpyObj<AuthService> & { user$: Observable<AuthUser> };

  const pendingUser: AuthUser = {
    id: 1,
    email: 'user@example.com',
    full_name: 'Test User',
    role: 'user',
    status: 'pending',
    email_verified_at: null
  };

  beforeEach(async () => {
    authService = Object.assign(
      jasmine.createSpyObj<AuthService>('AuthService', ['resendVerification', 'logout']),
      { user$: of(pendingUser) }
    );
    await TestBed.configureTestingModule({
      imports: [VerificationSentComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: authService }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(VerificationSentComponent);
    component = fixture.componentInstance;
  });

  afterEach(() => TestBed.resetTestingModule());

  it('starts a visible cooldown after resending', fakeAsync(() => {
    authService.resendVerification.and.returnValue(of({ message: 'Correo enviado' }));

    component.resend();
    tick(1000);

    expect(component.state).toBe('sent');
    expect(component.cooldownSeconds).toBe(59);
    fixture.destroy();
  }));

  it('uses Retry-After when the backend applies its cooldown', fakeAsync(() => {
    authService.resendVerification.and.returnValue(throwError(() =>
      new HttpErrorResponse({
        status: 429,
        headers: new HttpHeaders({ 'Retry-After': '12' })
      })
    ));

    component.resend();
    tick(1000);

    expect(component.cooldownSeconds).toBe(11);
    expect(component.message).toContain('cuenta atrás');
    fixture.destroy();
  }));
});
