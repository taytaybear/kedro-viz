from dataclasses import dataclass
from pathlib import Path
from typing import Dict
from unittest import mock

import pytest
from fastapi.testclient import TestClient

try:
    from kedro_datasets import (  # isort:skip
        pandas,
        tracking,
    )
except ImportError:
    from kedro.extras.datasets import (  # Safe since ImportErrors are suppressed within kedro.
        pandas,
        tracking,
    )

from kedro.io import DataCatalog, MemoryDataSet, Version
from kedro.pipeline import Pipeline, node
from kedro.pipeline.modular_pipeline import pipeline

from kedro_viz.api import apps
from kedro_viz.data_access import DataAccessManager
from kedro_viz.server import populate_data


@pytest.fixture
def data_access_manager():
    yield DataAccessManager()


@pytest.fixture
def example_pipelines():
    def process_data(raw_data, train_test_split):
        ...

    def train_model(model_inputs, parameters):
        ...

    data_processing_pipeline = pipeline(
        [
            node(
                process_data,
                inputs=["raw_data", "params:train_test_split"],
                outputs="model_inputs",
                name="process_data",
                tags=["split"],
            )
        ],
        namespace="uk.data_processing",
        outputs="model_inputs",
    )
    data_science_pipeline = pipeline(
        [
            node(
                train_model,
                inputs=["model_inputs", "parameters"],
                outputs="model",
                name="train_model",
                tags=["train"],
            )
        ],
        namespace="uk.data_science",
        inputs="model_inputs",
    )
    yield {
        "__default__": data_processing_pipeline + data_science_pipeline,
        "data_science": data_science_pipeline,
        "data_processing": data_processing_pipeline,
    }


@pytest.fixture
def example_catalog():
    yield DataCatalog(
        data_sets={
            "uk.data_processing.raw_data": pandas.CSVDataSet(filepath="raw_data.csv"),
            "model_inputs": pandas.CSVDataSet(filepath="model_inputs.csv"),
            "uk.data_science.model": MemoryDataSet(),
        },
        feed_dict={
            "parameters": {"train_test_split": 0.1, "num_epochs": 1000},
            "params:uk.data_processing.train_test_split": 0.1,
        },
        layers={
            "raw": {
                "uk.data_processing.raw_data",
            },
            "model_inputs": {"model_inputs"},
        },
    )


@pytest.fixture
def example_transcoded_pipelines():
    def process_data(raw_data, train_test_split):
        ...

    def train_model(model_inputs, parameters):
        ...

    data_processing_pipeline = pipeline(
        [
            node(
                process_data,
                inputs=["raw_data", "params:uk.data_processing.train_test_split"],
                outputs="model_inputs@pandas2",
                name="process_data",
                tags=["split"],
            ),
            node(
                train_model,
                inputs=["model_inputs@pandas", "parameters"],
                outputs="model",
                name="train_model",
                tags=["train"],
            ),
        ]
    )

    yield {
        "__default__": data_processing_pipeline,
        "data_processing": data_processing_pipeline,
    }


@pytest.fixture
def example_transcoded_catalog():
    yield DataCatalog(
        data_sets={
            "model_inputs@pandas": pandas.ParquetDataSet(
                filepath="model_inputs.parquet"
            ),
            "model_inputs@pandas2": pandas.CSVDataSet(filepath="model_inputs.csv"),
        },
        feed_dict={
            "parameters": {"train_test_split": 0.1, "num_epochs": 1000},
            "params:uk.data_processing.train_test_split": 0.1,
        },
    )


@pytest.fixture
def example_api(
    data_access_manager: DataAccessManager,
    example_pipelines: Dict[str, Pipeline],
    example_catalog: DataCatalog,
    mocker,
):
    api = apps.create_api_app_from_project(mock.MagicMock())
    populate_data(data_access_manager, example_catalog, example_pipelines, None)
    mocker.patch(
        "kedro_viz.api.rest.responses.data_access_manager", new=data_access_manager
    )
    mocker.patch(
        "kedro_viz.api.rest.router.data_access_manager", new=data_access_manager
    )
    yield api


@pytest.fixture
def example_api_no_default_pipeline(
    data_access_manager: DataAccessManager,
    example_pipelines: Dict[str, Pipeline],
    example_catalog: DataCatalog,
    mocker,
):
    del example_pipelines["__default__"]
    api = apps.create_api_app_from_project(mock.MagicMock())
    populate_data(data_access_manager, example_catalog, example_pipelines, None)
    mocker.patch(
        "kedro_viz.api.rest.responses.data_access_manager", new=data_access_manager
    )
    mocker.patch(
        "kedro_viz.api.rest.router.data_access_manager", new=data_access_manager
    )
    yield api


@pytest.fixture
def example_transcoded_api(
    data_access_manager: DataAccessManager,
    example_transcoded_pipelines: Dict[str, Pipeline],
    example_transcoded_catalog: DataCatalog,
    mocker,
):
    api = apps.create_api_app_from_project(mock.MagicMock())
    populate_data(
        data_access_manager,
        example_transcoded_catalog,
        example_transcoded_pipelines,
        None,
    )
    mocker.patch(
        "kedro_viz.api.rest.responses.data_access_manager", new=data_access_manager
    )
    mocker.patch(
        "kedro_viz.api.rest.router.data_access_manager", new=data_access_manager
    )
    yield api


@pytest.fixture
def example_run_ids():
    yield ["2021-11-03T18.24.24.379Z", "2021-11-02T18.24.24.379Z"]


@pytest.fixture
def example_multiple_run_tracking_dataset(example_run_ids, tmp_path):
    new_metrics_dataset = tracking.MetricsDataSet(
        filepath=Path(tmp_path / "test.json").as_posix(),
        version=Version(None, example_run_ids[1]),
    )
    new_metrics_dataset.save({"col1": 1, "col3": 3})
    new_metrics_dataset = tracking.MetricsDataSet(
        filepath=Path(tmp_path / "test.json").as_posix(),
        version=Version(None, example_run_ids[0]),
    )
    new_data = {"col1": 3, "col2": 3.23}
    new_metrics_dataset.save(new_data)

    yield new_metrics_dataset


@pytest.fixture
def client(example_api):
    yield TestClient(example_api)


@pytest.fixture
def mock_http_response():
    @dataclass(frozen=True)
    class MockHTTPResponse:
        data: dict

        def json(self):
            return self.data

    return MockHTTPResponse
