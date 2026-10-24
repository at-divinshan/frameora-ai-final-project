"""Shared ORM metadata; declaring this base does not create database tables."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
