import os

from .base import DockerLogin, Image, Autoscaling

if os.environ.get("IS_DEPLOYMENT", False):
    from .serve import Deployment
else:
    from .deploy import Deployment

__all__ = ["Deployment", "DockerLogin", "Image", "Autoscaling"]
