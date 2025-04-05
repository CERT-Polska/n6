import { render, getByRole } from '@testing-library/react';
import OrganizationHeader from './OrganizationHeader';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { format } from 'date-fns';

describe('<OrganizationHeader />', () => {
  it.each([
    { range: 1, expHeader: '1 day' },
    {
      range: 1111,
      expHeader: `Last 1111 days`
    }
  ])('renders header component with basic org and update info', ({ range, expHeader }) => {
    const name = 'test_name';
    const at = new Date().toISOString(); // yyyy-MM-ddTHH:mm:ss.SSSX format, as per /dashboard API wiki
    const { container } = render(
      <LanguageProviderTestWrapper>
        <OrganizationHeader name={name} range={range} at={at} />
      </LanguageProviderTestWrapper>
    );
    const row = container.firstChild?.firstChild as HTMLElement;
    const cols = row.childNodes as NodeListOf<HTMLElement>;
    expect(cols).toHaveLength(2); // name and joint column for last update, data range
    expect(getByRole(cols[0], 'heading', { level: 2 })).toHaveTextContent(name);
    const subcols = cols[1].firstChild?.childNodes as NodeListOf<HTMLElement>;
    expect(subcols).toHaveLength(2); // last update and data range;
    expect(subcols[0]).toHaveTextContent(`Last update${format(new Date(at), 'dd.MM.yyyy, HH:mm')}`);
    expect(subcols[1]).toHaveTextContent(`Data range${expHeader}`);
  });
});
