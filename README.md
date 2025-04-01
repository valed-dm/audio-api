# audio-api
FastAPI service for audio file uploads with Yandex user authentication and local storage. Built with FastAPI, SQLAlchemy, and Docker. Supports secure file storage and user management.

Приложение для загрузки аудиофайлов с возможной авторизацией как через яндекс, так и по собственному эндпоинту.
Авторизация на яндексе пройдена, необходимы технические работы по проверке взаимодействия двух моделей авторизации,
кастомному логгеру, реализации загрузки аудио. Принципиально вопрос двойной авторизации решен.
Объем работ вышел за рамки установленного дедлайна 48 часов.
Качество на усмотрение ревьюера. Нужен дополнительный рефактор - срок для завершения 20 - 30 часов.

Текущее состояние уже исправлено:
[<img src="docs/images/img_01.png" width="800"/>]()

Авторизация Яндекс отлично работает, данные пользователя созраняются в БД.
Дополнительно указывается способ авторизации (Яндекс, приложение).
[<img src="docs/images/img_02.png" width="300"/>]()

Логирование полностью настроено
[<img src="docs/images/img_03.png" width="800"/>]()

Модель авторизации позволяет администратору настраивать индивидуальный доступ к каждому эндпоинту
для каждого пользователя (использована схема tiangolo 'scopes')


[<img src="docs/images/img_05.png" width="800"/>]()

[<img src="docs/images/img_06.png" width="400"/>]()

[<img src="docs/images/img_07.png" width="400"/>]()

[<img src="docs/images/img_08.png" width="400"/>]()

[<img src="docs/images/img_09.png" width="800"/>]()

[<img src="docs/images/img_10.png" width="800"/>]()

[<img src="docs/images/img_11.png" width="800"/>]()

[<img src="docs/images/img_12.png" width="800"/>]()

Образец загруженного файла в папке "/storage".
