IMAGE_NAME=hv2pve
IMAGE_VER=latest

run:
	@python3 ./run.py -v 1

debug:
	@python3 ./run.py -v 2

build:
	@docker image  prune -f
	@docker build --progress=plain  -t $(IMAGE_NAME):$(IMAGE_VER) .

buildNoCache:
	@docker build --no-cache -t $(IMAGE_NAME):$(IMAGE_VER) .

rund:
	docker run --network host -v $(shell pwd)/env.json:/usr/src/app/env.json --rm $(IMAGE_NAME):$(IMAGE_VER) 

clean:
	@python3 ./run_clean.py -v 1

re: clean run

dryrun:
	@python3 ./run.py --dry-run -v 1