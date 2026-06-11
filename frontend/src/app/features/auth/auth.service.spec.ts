import { sanitizeReturnUrl } from './auth.service';

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
