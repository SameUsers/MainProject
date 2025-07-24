def register_swagger_path(swagger):
    swagger.add_path(
    path="/authorization",
    method="post",
    summary="Регистрация пользователя и получение токена",
    tags=["Авторизация"],
    description="""
    Регистрирует нового пользователя и выдает ему токен.

    Требуется передать JSON-объект в теле запроса с обязательным полем:
    - username: имя нового пользователя

    Возвращает токен и лимит времени, связанный с пользователем.
    """,
    request_body={
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "username": {
                            "type": "string",
                            "example": "myusername",
                            "description": "Имя нового пользователя"
                        }
                    },
                    "required": ["username"]
                }
            }
        }
    },
    responses={
        "200": {
            "description": "Пользователь успешно зарегистрирован",
            "content": {
                "application/json": {
                    "example": {
                        "username": "myusername",
                        "token": "generated_token_123",
                        "time_limit": 600
                    }
                }
            }
        },
        "400": {
            "description": "Ошибка запроса или пользователь уже существует",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_body": {
                            "summary": "Отсутствует тело запроса",
                            "value": {
                                "Ошибка": "В теле запроса отсутствует JSON-Body"
                            }
                        },
                        "missing_username": {
                            "summary": "Не указано имя пользователя",
                            "value": {
                                "Ошибка": "Имя для пользователя не указано"
                            }
                        },
                        "duplicate_user": {
                            "summary": "Пользователь уже существует",
                            "value": {
                                "Ошибка": "Пользователь с таким именем уже существует"
                            }
                        }
                    }
                }
            }
        }
    }
)
    swagger.add_path(
    path="/status",
    method="get",
    summary="Получить список задач по статусу",
    tags=["Статусы"],
    description="""
    Возвращает список задач пользователя.  
    Если параметр status не передан, возвращаются все задачи.

    Поддерживается пагинация через параметры page и per_page.

    Допустимые значения параметра status:  
    - queue (ожидает)  
    - process (в обработке)  
    - done (готово)  
    - error (ошибка)  

    ⚠️ Требуется авторизация через Bearer Token.
    """,
    parameters=[
        {
            "name": "status",
            "in": "query",
            "required": False,
            "schema": {
                "type": "string",
                "enum": ["queue", "process", "done", "error"]
            },
            "description": "Фильтрация задач по статусу. Если не указан, возвращаются все задачи пользователя."
        },
        {
            "name": "page",
            "in": "query",
            "required": False,
            "schema": {
                "type": "integer",
                "default": 1
            },
            "description": "Номер страницы пагинации (по умолчанию 1)"
        },
        {
            "name": "per_page",
            "in": "query",
            "required": False,
            "schema": {
                "type": "integer",
                "default": 10
            },
            "description": "Количество задач на странице (по умолчанию 10)"
        }
    ],
    responses={
        "200": {
            "description": "Успешный ответ. Возвращает задачи пользователя.",
            "content": {
                "application/json": {
                    "example": {
                        "page": 1,
                        "per_page": 10,
                        "total_tasks": 17,
                        "total_pages": 2,
                        "tasks": [
                            {
                                "task_id": "abc123",
                                "status_code": "200",
                                "status_message": "Задача успешно завершена и готова к загрузке"
                            },
                            {
                                "task_id": "xyz789",
                                "status_code": "100",
                                "status_message": "Задача в процессе обработки"
                            }
                        ]
                    }
                }
            }
        },
        "400": {
            "description": "Некорректный статус",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Некорректный статус. Допустимые значения: queue, process, done, error"
                    }
                }
            }
        }
    },
    security=[{"ApiTokenAuth": []}]
)
    
    swagger.add_path(
    path="/status/task_id",
    method="get",
    summary="Получение статуса задачи",
    tags=["Статусы"],
    description="""
    Получить статус задачи по task_id.

    Требуется токен авторизации в заголовке:
    Authorization: Bearer <token>

    Параметры запроса:
    - task_id (обязательный): идентификатор задачи.

    Возвращает текущий статус задачи.
    """,
    parameters=[
        {
            "name": "task_id",
            "in": "query",
            "required": True,
            "schema": {
                "type": "string"
            },
            "description": "Идентификатор задачи"
        }
    ],
    responses={
        "200": {
            "description": "Информация о статусе задачи",
            "content": {
                "application/json": {
                    "example": {
                        "Статус": "100",
                        "ID-задачи": "abc123"
                    }
                }
            }
        },
        "400": {
            "description": "Отсутствует обязательный параметр task_id",
            "content": {
                "application/json": {
                    "example": {
                        "Ошибка": "Параметр 'task_id' обязателен"
                    }
                }
            }
        },
        "404": {
            "description": "Задача не найдена",
            "content": {
                "application/json": {
                    "example": {
                        "Ошибка": "Задача не найдена"
                    }
                }
            }
        }
    }
)
    swagger.add_path(
    path="/task",
    method="post",
    summary="Отправка аудиофайлов в очередь обработки",
    tags=["Задачи"],
    description="""
    Принимает один или несколько аудиофайлов и ставит задачи в очередь на обработку.

    Требуется передать JWT-токен в заголовке:
    Authorization: Bearer <token>

    Флаг диаризации:
    - with_diarization (опционально) — булево значение (true/false).
      Если указать true, транскрипция будет включать диаризацию спикеров.

    Тело запроса должно быть типа multipart/form-data, 
    где параметр audio — массив аудиофайлов.

    Поддерживаемые форматы: wav, mp3, flac, ogg, mp4, aac, wma
    """,
    request_body={
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "audio": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "format": "binary"
                            },
                            "description": "Один или несколько аудиофайлов"
                        },
                        "with_diarization": {
                            "type": "boolean",
                            "description": "Флаг включения диаризации (по умолчанию false)"
                        }
                    },
                    "required": ["audio"]
                }
            }
        }
    },
    responses={
        "200": {
            "description": "Список успешно поставленных задач",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "task_id": "abc123",
                            "file_name": "audio1.wav",
                            "audio_duration": 120,
                            "remaining_time": 300,
                            "with_diarization": False
                        },
                        {
                            "task_id": "def456",
                            "file_name": "audio2.mp3",
                            "audio_duration": 60,
                            "remaining_time": 240,
                            "with_diarization": True
                        }
                    ]
                }
            }
        },
        "400": {
            "description": "Ошибка валидации, неподдерживаемый формат или недостаточно времени",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Недостаточно времени. Осталось: 10 сек, требуется: 30 сек."
                    }
                }
            }
        }
    }
)    
    swagger.add_path(
    path="/download",
    method="get",
    summary="Скачивание результата распознавания",
    tags=["Задачи"],
    description="""
    Позволяет скачать результат задачи по task_id.

    Требуется передать параметры в query string:
    - task_id — ID задачи
    - type — формат файла для скачивания (`txt` или `json`)

    ⚠️ Требуется авторизация через токен (Bearer Token в заголовке Authorization).
    """,
    parameters=[
        {
            "name": "task_id",
            "in": "query",
            "required": True,
            "schema": {
                "type": "string",
                "example": "abc123"
            },
            "description": "Уникальный идентификатор задачи"
        },
        {
            "name": "type",
            "in": "query",
            "required": True,
            "schema": {
                "type": "string",
                "enum": ["txt", "json"],
                "example": "json"
            },
            "description": "Формат запрашиваемого файла (txt или json)"
        }
    ],
    responses={
        "200": {
            "description": "Файл успешно найден и отправлен клиенту"
        },
        "400": {
            "description": "Некорректный запрос (например, отсутствуют параметры или тип файла недопустим)",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_params": {
                            "summary": "Не указаны обязательные параметры",
                            "value": {
                                "Ошибка": "Необходимо указать task_id и тип файла (type=txt|json)"
                            }
                        },
                        "invalid_type": {
                            "summary": "Неверный тип файла",
                            "value": {
                                "Ошибка": "Тип файла должен быть либо txt, либо json"
                            }
                        }
                    }
                }
            }
        },
        "404": {
            "description": "Файл или задача не найдены",
            "content": {
                "application/json": {
                    "example": {
                        "Ошибка": "Задача не найдена или доступ запрещён"
                    }
                }
            }
        },
        "500": {
            "description": "Непредвиденная ошибка при скачивании",
            "content": {
                "application/json": {
                    "example": {
                        "Ошибка": "Непредвиденная ошибка: <текст_ошибки>"
                    }
                }
            }
        }
    },
    security=[{"ApiTokenAuth": []}]
)
    