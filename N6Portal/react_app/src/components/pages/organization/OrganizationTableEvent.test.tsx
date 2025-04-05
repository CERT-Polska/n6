import { render, screen, getAllByText } from '@testing-library/react';
import OrganizationTableEvent from './OrganizationTableEvent';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';

describe('<OrganizationTableEvent />', () => {
  it('renders basic table with given entries', () => {
    const eventEntry: Record<number, Record<string, number> | null> = {
      1: { test_name_1: 1111 },
      2: null,
      3: { test_name_3: 3333 }
    };
    render(
      <LanguageProviderTestWrapper>
        <OrganizationTableEvent eventEntry={eventEntry} eventKey="mockedEventKey" />
      </LanguageProviderTestWrapper>
    );
    const columnHeaders = screen.getAllByRole('columnheader');
    const rows = screen.getAllByRole('row');
    expect(rows).toHaveLength(Object.keys(eventEntry).length + 1);
    expect(screen.getAllByRole('cell')).toHaveLength(Object.keys(eventEntry).length * 3);
    expect(columnHeaders).toHaveLength(3);
    expect(columnHeaders[0]).toHaveTextContent('No.');
    expect(columnHeaders[1]).toHaveTextContent('Name');
    expect(columnHeaders[2]).toHaveTextContent('Events count');
    expect(getAllByText(rows[2], '-')).toHaveLength(2); // two empty slots
    expect(screen.getByText(Object.keys(eventEntry)[1])).toBeInTheDocument();
    expect(screen.getByText(Object.keys(eventEntry[1] as Record<string, number>)[0])).toBeInTheDocument();
    expect(screen.getByText(Object.values(eventEntry[1] as Record<string, number>)[0])).toBeInTheDocument();
  });
});
