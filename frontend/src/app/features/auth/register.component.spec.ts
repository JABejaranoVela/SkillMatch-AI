import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { of } from 'rxjs';

import { AuthService } from './auth.service';
import { RegisterComponent } from './register.component';

describe('RegisterComponent', () => {
  let fixture: ComponentFixture<RegisterComponent>;
  let component: RegisterComponent;
  let authService: jasmine.SpyObj<AuthService>;
  let router: Router;

  beforeEach(async () => {
    authService = jasmine.createSpyObj<AuthService>('AuthService', ['register']);
    await TestBed.configureTestingModule({
      imports: [RegisterComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: authService }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(RegisterComponent);
    component = fixture.componentInstance;
    router = TestBed.inject(Router);
  });

  afterEach(() => TestBed.resetTestingModule());

  it('rejects a mismatched password confirmation', () => {
    component.form.setValue({
      fullName: 'Test User',
      email: 'user@example.com',
      password: 'valid-password',
      confirmPassword: 'different-password'
    });

    component.submit();

    expect(component.form.controls.confirmPassword.hasError('mismatch')).toBeTrue();
    expect(authService.register).not.toHaveBeenCalled();
  });

  it('redirects to the generic verification screen after registration', () => {
    const navigateSpy = spyOn(router, 'navigateByUrl');
    authService.register.and.returnValue(of({ message: 'Cuenta creada' }));
    component.form.setValue({
      fullName: 'Test User',
      email: 'user@example.com',
      password: 'valid-password',
      confirmPassword: 'valid-password'
    });

    component.submit();

    expect(navigateSpy).toHaveBeenCalledWith('/verify-email-sent');
  });
});
