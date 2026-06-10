import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { AuthService } from './auth.service';
import { ForgotPasswordComponent } from './forgot-password.component';

describe('ForgotPasswordComponent', () => {
  let fixture: ComponentFixture<ForgotPasswordComponent>;
  let component: ForgotPasswordComponent;
  let authService: jasmine.SpyObj<AuthService>;

  beforeEach(async () => {
    authService = jasmine.createSpyObj<AuthService>('AuthService', ['forgotPassword']);
    await TestBed.configureTestingModule({
      imports: [ForgotPasswordComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: authService }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(ForgotPasswordComponent);
    component = fixture.componentInstance;
  });

  afterEach(() => TestBed.resetTestingModule());

  it('does not submit an invalid email', () => {
    component.form.controls.email.setValue('not-an-email');

    component.submit();

    expect(component.form.controls.email.touched).toBeTrue();
    expect(authService.forgotPassword).not.toHaveBeenCalled();
  });

  it('shows the generic success response', () => {
    authService.forgotPassword.and.returnValue(of({
      message: 'Si existe una cuenta, recibiras instrucciones'
    }));
    component.form.controls.email.setValue('user@example.com');

    component.submit();

    expect(authService.forgotPassword).toHaveBeenCalledWith('user@example.com');
    expect(component.state).toBe('sent');
    expect(component.message).toContain('Si existe una cuenta');
  });
});
