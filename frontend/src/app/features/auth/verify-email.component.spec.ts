import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { AuthService } from './auth.service';
import { VerifyEmailComponent } from './verify-email.component';

describe('VerifyEmailComponent', () => {
  let fixture: ComponentFixture<VerifyEmailComponent>;
  let authService: jasmine.SpyObj<AuthService> & { user$: ReturnType<typeof of> };
  let router: Router;

  async function createComponent(token: string | null = 'valid-token'): Promise<void> {
    authService = jasmine.createSpyObj<AuthService>(
      'AuthService',
      ['verifyEmail', 'logoutCurrentSession'],
      { user$: of(null) }
    ) as jasmine.SpyObj<AuthService> & { user$: ReturnType<typeof of> };
    authService.verifyEmail.and.returnValue(
      of({ message: 'Correo verificado correctamente' })
    );
    authService.logoutCurrentSession.and.returnValue(of(undefined));

    await TestBed.configureTestingModule({
      imports: [VerifyEmailComponent],
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: authService
        },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { queryParamMap: convertToParamMap(token ? { token } : {}) }
          }
        }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(VerifyEmailComponent);
    router = TestBed.inject(Router);
    fixture.detectChanges();
  }

  afterEach(() => TestBed.resetTestingModule());

  it('shows login action after a successful verification', async () => {
    await createComponent();

    const text = fixture.nativeElement.textContent as string;

    expect(text).toContain('Correo verificado');
    expect(text).toContain('Iniciar sesión');
    expect(text).not.toContain('Ir a mi CV');
  });

  it('logs out any previous session before going to login', async () => {
    await createComponent();
    const navigateSpy = spyOn(router, 'navigate');

    const button = fixture.nativeElement.querySelector('button.primary-action') as HTMLButtonElement;
    button.click();

    expect(authService.logoutCurrentSession).toHaveBeenCalled();
    expect(navigateSpy).toHaveBeenCalledWith(['/login'], {
      queryParams: { reason: 'verified' }
    });
  });

  it('goes to login even if clearing a previous session fails', async () => {
    await createComponent();
    const navigateSpy = spyOn(router, 'navigate');
    authService.logoutCurrentSession.and.returnValue(throwError(() => ({ status: 401 })));

    const button = fixture.nativeElement.querySelector('button.primary-action') as HTMLButtonElement;
    button.click();

    expect(navigateSpy).toHaveBeenCalledWith(['/login'], {
      queryParams: { reason: 'verified' }
    });
  });
});
