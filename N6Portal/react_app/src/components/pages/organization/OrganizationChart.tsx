import { FC } from 'react';
import classNames from 'classnames';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { Col, Row } from 'react-bootstrap';
import { categoryColor } from 'api/services/barChart/types';
import { useBarChart } from 'api/services/barChart';
import ApiLoader from 'components/loading/ApiLoader';
import { isCategory } from 'utils/isCategory';
import { useTypedIntl } from 'utils/useTypedIntl';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const options: ChartOptions<'bar'> = {
  plugins: {
    tooltip: {
      enabled: true,
      itemSort: (a, b) => b.datasetIndex - a.datasetIndex,
      filter: (tooltipItem) => !!tooltipItem?.raw
    },
    legend: {
      position: 'bottom' as const,
      align: 'start' as const,
      labels: {
        boxWidth: 20,
        boxHeight: 20,
        filter: (item, data) => data.datasets[item.datasetIndex as number].data.some((value) => !!value)
      }
    }
  },
  maintainAspectRatio: false,
  responsive: true,
  interaction: {
    mode: 'index' as const,
    intersect: false
  },
  scales: {
    x: {
      stacked: true
    },
    y: {
      stacked: true,
      ticks: {
        stepSize: 10
      }
    }
  }
};

const OrganizationChart: FC = () => {
  const { messages } = useTypedIntl();
  const { data, status, error } = useBarChart();

  if (!data && status !== 'loading') return null;

  return (
    <div className="content-wrapper">
      <Row>
        <Col sm="12" className="mb-4">
          <div className={classNames('organization-card', { 'empty-chart': data?.empty_dataset })}>
            <ApiLoader status={status} error={error}>
              {data?.empty_dataset ? (
                <h3 className="mb-0">{`${messages['organization_chart_no_data']} ${data.days_range} ${messages['organization_chart_no_data_sentence_end']}`}</h3>
              ) : (
                <Bar
                  width="400px"
                  height="450px"
                  options={options}
                  data={{
                    labels: data?.days,
                    datasets: Object.entries(data?.datasets || {}).map(([key, entry]) => ({
                      label: key,
                      data: entry,
                      backgroundColor: isCategory(key) ? categoryColor[key] : '#008bf8'
                    }))
                  }}
                />
              )}
            </ApiLoader>
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default OrganizationChart;
