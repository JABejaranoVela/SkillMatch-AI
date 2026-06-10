import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { AuthService } from '../auth/auth.service';
import { SettingsComponent } from './settings.component';

describe('SettingsComponent', () => {
  let fixture: ComponentFixture<SettingsComponent>;
  let component: SettingsComponent;
  let authService: jasmine.SpyObj<AuthService>;

  beforeEach(async () => {
    authService = jasmine.createSpyObj<AuthService>(
      'AuthService',
      ['changePassword', 'logout']
    );
    await TestBed.configureTestingModule({
      imports: [SettingsComponent],
      providers: [{ provide: AuthService, useValue: authService }]
    }).compileComponents();
    fixture = TestBed.createComponent(SettingsComponent);
    component = fixture.componentInstance;
  });

  afterEach(() => TestBed.resetTestingModule());

  it('requires a password of at least ten characters', () => {
    component.form.setValue({
      currentPassword: 'old-password',
      newPassword: 'short',
      confirmPassword: 'short'
    });

    component.submit();

    expect(component.form.controls.newPassword.hasError('minlength')).toBeTrue();
    expect(authService.changePassword).not.toHaveBeenCalled();
  });

  it('marks mismatched confirmation', () => {
    component.form.setValue({
      currentPassword: 'old-password',
      newPassword: 'new-password-123',
      confirmPassword: 'different-password'
    });

    component.submit();

    expect(component.form.controls.confirmPassword.hasError('mismatch')).toBeTrue();
    expect(authService.changePassword).not.toHaveBeenCalled();
  });

  it('sends all three password fields and shows success', () => {
    authService.changePassword.and.returnValue(of({
      message: 'Contrasena actualizada correctamente'
    }));
    component.form.setValue({
      currentPassword: 'old-password',
      newPassword: 'new-password-123',
      confirmPassword: 'new-password-123'
    });

    component.submit();

    expect(authService.changePassword).toHaveBeenCalledWith(
      'old-password',
      'new-password-123',
      'new-password-123'
    );
    expect(component.statusMessage).toContain('actualizada');
  });
});
