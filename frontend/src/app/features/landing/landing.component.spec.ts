import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { BehaviorSubject, Subject, of, throwError } from 'rxjs';

import { AuthService } from '../auth/auth.service';
import { LandingComponent } from './landing.component';
import { PublicDemoAnalysis, PublicDemoService } from './public-demo.service';

describe('LandingComponent public demo', () => {
  let fixture: ComponentFixture<LandingComponent>;
  let component: LandingComponent;
  let authenticatedSubject: BehaviorSubject<boolean>;
  let demoService: jasmine.SpyObj<PublicDemoService>;

  const result: PublicDemoAnalysis = {
    profile_type: 'Full Stack Developer',
    summary: 'Perfil técnico con experiencia web.',
    skills: ['Angular', 'Python', 'Docker'],
    languages: ['Español', 'Inglés'],
    education: ['Grado Superior en Desarrollo de Aplicaciones'],
    experience_summary: '3 años de experiencia detectados',
    is_demo: true
  };

  beforeEach(async () => {
    authenticatedSubject = new BehaviorSubject(false);
    demoService = jasmine.createSpyObj<PublicDemoService>(
      'PublicDemoService',
      ['analyzeCv']
    );

    await TestBed.configureTestingModule({
      imports: [LandingComponent],
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: { authenticated$: authenticatedSubject.asObservable() }
        },
        { provide: PublicDemoService, useValue: demoService }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(LandingComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => TestBed.resetTestingModule());

  function selectPdf(): File {
    const file = new File(['pdf'], 'cv.pdf', { type: 'application/pdf' });
    component.demoFile = file;
    component.demoState = 'selected';
    fixture.detectChanges();
    return file;
  }

  it('renders the public CV demo section', () => {
    const demo = fixture.nativeElement.querySelector('#demo-cv');

    expect(demo).not.toBeNull();
    expect(demo.textContent).toContain('Sube tu CV y descubre qué perfil detecta');
  });

  it('keeps the desktop navigation in the same order as the landing sections', () => {
    const links = Array.from(
      fixture.nativeElement.querySelectorAll('.desktop-nav a')
    ) as HTMLAnchorElement[];

    expect(links.map((link) => link.textContent?.trim())).toEqual([
      'Cómo funciona',
      'Demo CV',
      'Analiza tu CV',
      'Ofertas compatibles',
      'Para quién es',
      'Acceder'
    ]);
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '#como-funciona',
      '#demo-cv',
      '#analiza-cv',
      '#ofertas-compatibles',
      '#para-quien-es',
      '/login'
    ]);
  });

  it('uses the same ordered anchors in the mobile menu and closes it after navigation', () => {
    component.mobileMenuOpen = true;
    fixture.detectChanges();
    const links = Array.from(
      fixture.nativeElement.querySelectorAll('.mobile-nav a')
    ) as HTMLAnchorElement[];

    expect(links.slice(0, 6).map((link) => link.textContent?.trim())).toEqual([
      'Cómo funciona',
      'Demo CV',
      'Analiza tu CV',
      'Ofertas compatibles',
      'Para quién es',
      'Acceder'
    ]);

    links[1].addEventListener('click', (event) => event.preventDefault(), { once: true });
    links[1].dispatchEvent(new MouseEvent('click', {
      bubbles: true,
      cancelable: true
    }));
    expect(component.mobileMenuOpen).toBeFalse();
  });

  it('renders the anchor sections once and in forward navigation order', () => {
    const expectedIds = [
      'como-funciona',
      'demo-cv',
      'analiza-cv',
      'ofertas-compatibles',
      'para-quien-es'
    ];
    const sections = fixture.nativeElement.querySelectorAll(
      'main section[id]'
    ) as NodeListOf<HTMLElement>;
    const elementsWithId = fixture.nativeElement.querySelectorAll(
      '[id]'
    ) as NodeListOf<HTMLElement>;
    const orderedIds = Array.from(sections, (section) => section.id);
    const allIds = Array.from(elementsWithId, (element) => element.id);

    expect(orderedIds).toEqual(expectedIds);
    expect(new Set(allIds).size).toBe(allIds.length);
  });

  it('sends anonymous upload CTAs to the public demo', () => {
    const headerCta = fixture.nativeElement.querySelector('.header-cta');
    const heroCta = fixture.nativeElement.querySelector('.hero-actions .primary-button');

    expect(headerCta.getAttribute('href')).toBe('#demo-cv');
    expect(heroCta.getAttribute('href')).toBe('#demo-cv');
  });

  it('sends authenticated upload CTAs to the real CV flow', () => {
    authenticatedSubject.next(true);
    fixture.detectChanges();
    const headerCta = fixture.nativeElement.querySelector('.header-cta');
    const heroCta = fixture.nativeElement.querySelector('.hero-actions .primary-button');

    expect(headerCta.getAttribute('href')).toBe('/resumes');
    expect(heroCta.getAttribute('href')).toBe('/resumes');
  });

  it('shows the loading state while the PDF is analyzed', () => {
    const pending = new Subject<PublicDemoAnalysis>();
    demoService.analyzeCv.and.returnValue(pending.asObservable());
    selectPdf();

    component.analyzeDemoCv();
    fixture.detectChanges();

    expect(component.demoState).toBe('loading');
    expect(fixture.nativeElement.querySelector('#demo-cv').textContent)
      .toContain('Analizando tu CV');
  });

  it('renders the detected profile and optional sections', () => {
    demoService.analyzeCv.and.returnValue(of(result));
    const file = selectPdf();

    component.analyzeDemoCv();
    fixture.detectChanges();

    const demo = fixture.nativeElement.querySelector('#demo-cv');
    expect(demoService.analyzeCv).toHaveBeenCalledWith(file);
    expect(component.demoState).toBe('success');
    expect(demo.textContent).toContain('Full Stack Developer');
    expect(demo.textContent).toContain('Angular');
    expect(demo.textContent).toContain('Grado Superior');
    expect(demo.textContent).toContain('Inglés');
    expect(demo.textContent).toContain('3 años de experiencia');
  });

  it('shows a controlled error without breaking the landing', () => {
    demoService.analyzeCv.and.returnValue(throwError(() => new HttpErrorResponse({
      status: 400,
      error: { detail: 'No se ha podido extraer suficiente texto del PDF' }
    })));
    selectPdf();

    component.analyzeDemoCv();
    fixture.detectChanges();

    expect(component.demoState).toBe('error');
    expect(fixture.nativeElement.querySelector('#demo-cv').textContent)
      .toContain('No se ha podido extraer suficiente texto');
    expect(fixture.nativeElement.querySelector('.hero-section')).not.toBeNull();
  });

  it('links anonymous users to registration after the analysis', () => {
    demoService.analyzeCv.and.returnValue(of(result));
    selectPdf();

    component.analyzeDemoCv();
    fixture.detectChanges();

    const link = fixture.nativeElement.querySelector('.demo-result-cta a');
    expect(link.getAttribute('href')).toBe('/register');
  });

  it('links authenticated users to the real CV flow', () => {
    authenticatedSubject.next(true);
    demoService.analyzeCv.and.returnValue(of(result));
    selectPdf();

    component.analyzeDemoCv();
    fixture.detectChanges();

    const link = fixture.nativeElement.querySelector('.demo-result-cta a');
    expect(link.getAttribute('href')).toBe('/resumes');
  });

  it('resets the selected file and result', () => {
    component.demoFile = new File(['pdf'], 'cv.pdf', { type: 'application/pdf' });
    component.demoResult = result;
    component.demoState = 'success';

    component.resetDemo();

    expect(component.demoState).toBe('idle');
    expect(component.demoFile).toBeNull();
    expect(component.demoResult).toBeNull();
  });

  it('does not expose job actions inside the public demo', () => {
    demoService.analyzeCv.and.returnValue(of(result));
    selectPdf();

    component.analyzeDemoCv();
    fixture.detectChanges();

    const demoText = fixture.nativeElement.querySelector('#demo-cv').textContent;
    expect(demoText).not.toContain('Guardar oferta');
    expect(demoText).not.toContain('Descartar oferta');
    expect(demoText).not.toContain('Postular');
  });
});
