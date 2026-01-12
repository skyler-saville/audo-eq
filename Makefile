.PHONY: install test process clean

install:
	poetry install

test:
	poetry run pytest tests/ -v

# Example command to process a track
process:
	poetry run python -m audo_eq.cli process \
		--target ./audio/my_track.wav \
		--reference ./audio/pro_reference.wav \
		--config ./configs/tra_heavy_rock.yaml \
		--output ./mastered/mastered.wav

lint:
	poetry run black src/ tests/

clean:
	rm -rf ./output/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete