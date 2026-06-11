import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { of } from 'rxjs';

import { AuthService } from './auth.service';
import { ResetPasswordComponent } from './reset-password.component';

describe('ResetPasswordComponent', () => {
  let authService: jasmine.SpyObj<AuthService>;

  async function createComponent(token: string | null): Promise<
    ComponentFixture<ResetPasswordComponent>
  > {
    authService = jasmine.createSpyObj<AuthService>('AuthService', ['resetPassword']);
    await TestBed.configureTestingModule({
      imports: [ResetPasswordComponent],
      providers: [
        { provide: AuthService, useValue: authService },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              queryParamMap: convertToParamMap(token ? { token } : {})
            }
          }
        }
      ]
    }).compileComponents();
    const fixture = TestBed.createComponent(ResetPasswordComponent);
    fixture.detectChanges();
    return fixture;
  }

  afterEach(() => TestBed.resetTestingModule());

  it('shows an error when the token is absent', async () => {
    const fixture = await createComponent(null);

    expect(fixture.componentInstance.state).toBe('invalid');
    expect(fixture.componentInstance.message).toContain('no es válido');
  });

  it('rejects a mismatched confirmation', async () => {
    const fixture = await createComponent('x'.repeat(48));
    const component = fixture.componentInstance;
    component.form.setValue({
      newPassword: 'new-password-123',
      confirmPassword: 'different-password'
    });

    component.submit();

    expect(component.form.controls.confirmPassword.hasError('mismatch')).toBeTrue();
    expect(authService.resetPassword).not.toHaveBeenCalled();
  });

  it('shows success and allows returning to login', async () => {
    const fixture = await createComponent('x'.repeat(48));
    const component = fixture.componentInstance;
    authService.resetPassword.and.returnValue(of({
      message: 'Contrasena restablecida correctamente'
    }));
    component.form.setValue({
      newPassword: 'new-password-123',
      confirmPassword: 'new-password-123'
    });

    component.submit();
    fixture.detectChanges();

    expect(component.state).toBe('success');
    expect(
      fixture.nativeElement.querySelector('.primary-action')?.getAttribute('href')
    ).toBe('/login');
  });
});
