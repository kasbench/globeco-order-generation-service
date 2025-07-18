docker buildx build --platform linux/amd64,linux/arm64  \
	--target production \
	-t kasbench/globeco-order-generation-service:latest \
	--push .
